"""Actual descendant cleanup and real OS console Ctrl+C (no injected exception)."""
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tests.blackbox import ROOT
from zzy.process import ProcessTree, run_bounded


class ProcessTests(unittest.TestCase):
    def test_descendants_reaped_on_timeout_overflow_normal_exit_and_cancel(self):
        for scenario in ("timeout", "overflow", "normal", "cancel"):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory(prefix="ZZY tree ") as directory:
                root = Path(directory)
                child = root / "child.py"
                child.write_text("import os,time\nfrom pathlib import Path\nheld=open('held','w')\nPath('grandchild').write_text(str(os.getpid()))\ntime.sleep(60)\n")
                parent = root / "parent.py"
                parent.write_text("import os,subprocess,sys,time\nfrom pathlib import Path\n"
                    "Path('parent').write_text(str(os.getpid()))\n"
                    "subprocess.Popen([sys.executable,'child.py'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
                    "while not Path('grandchild').exists(): time.sleep(.01)\n" +
                    ("print('x'*10000,flush=True)\ntime.sleep(60)" if scenario == "overflow" else
                     "" if scenario == "normal" else "time.sleep(60)"))
                actual_wait = subprocess.Popen.wait
                interrupted = False
                def interrupt(process, timeout=None):
                    nonlocal interrupted
                    if not interrupted and timeout == 2:
                        deadline = time.monotonic() + 2
                        while not (root / "grandchild").exists() and time.monotonic() < deadline:
                            time.sleep(.01)
                        interrupted = True
                        raise KeyboardInterrupt
                    return actual_wait(process, timeout=timeout)
                started = time.monotonic()
                with patch.object(subprocess.Popen, "wait", interrupt if scenario == "cancel" else actual_wait):
                    if scenario == "normal":
                        self.assertEqual(run_bounded([sys.executable, str(parent)], cwd=root, env=dict(os.environ), timeout=2), (0,b"",b""))
                    else:
                        error = {"timeout":subprocess.TimeoutExpired,"overflow":AssertionError,"cancel":KeyboardInterrupt}[scenario]
                        with self.assertRaises(error):
                            run_bounded([sys.executable,str(parent)],cwd=root,env=dict(os.environ),timeout=2,output_limit=16)
                self.assertLess(time.monotonic()-started, 8)
                for name in ("parent", "grandchild"):
                    pid = int((root/name).read_text())
                    self.assert_dead(pid)
            self.assertFalse(root.exists())

    def assert_dead(self, pid):
        if os.name == "nt":
            from ctypes import wintypes as W
            kernel = ctypes.WinDLL("kernel32",use_last_error=True)
            kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];kernel.OpenProcess.restype=W.HANDLE
            kernel.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];kernel.WaitForSingleObject.restype=W.DWORD
            kernel.CloseHandle.argtypes=[W.HANDLE]
            handle=kernel.OpenProcess(0x100000,False,pid)
            if handle:
                try:self.assertEqual(kernel.WaitForSingleObject(handle,5000),0,"descendant still alive")
                finally:kernel.CloseHandle(handle)
            else:self.assertEqual(ctypes.get_last_error(),87)
        else:
            # kill(0) can still see an already dead orphan zombie until init reaps it.
            status=Path(f"/proc/{pid}/stat")
            if status.exists():self.assertEqual(status.read_text().split()[2],"Z")
            else:
                with self.assertRaises(ProcessLookupError):os.kill(pid,0)

    def test_real_ctrl_c_run_and_spec_cleanup(self):
        for mode in ("run","test"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="ZZY console 中文 ") as directory:
                root=Path(directory); temporary=root/'temp';temporary.mkdir()
                ready=root/'ready'
                file=root/'interrupt.zzy'
                body='io.write_text("'+ready.as_posix()+'","ready");(while)(true){}'
                file.write_text(body if mode=='run' else '(spec) "interrupt" {'+body+'}',encoding='utf-8')
                tree=ProcessTree()
                kwargs={}
                if os.name=='nt':
                    startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
                    kwargs=dict(creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup)
                try:
                    process=tree.start([sys.executable,'-X','utf8','-m','zzy',mode,str(file),'--diagnostic-format','json'],
                        cwd=root,env=dict(os.environ,PYTHONPATH=str(ROOT),TEMP=str(temporary),TMP=str(temporary)),
                        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,**kwargs)
                    deadline=time.monotonic()+10
                    while not ready.exists() and process.poll() is None and time.monotonic()<deadline:time.sleep(.01)
                    self.assertTrue(ready.exists(),'program never reached ready point')
                    if os.name=='nt':
                        # Separate helper attaches only to the hidden child console.
                        # It ignores Ctrl+C itself; it never signals the test runner console.
                        script="import ctypes,sys,time; k=ctypes.WinDLL('kernel32'); k.FreeConsole(); assert k.AttachConsole(int(sys.argv[1])); assert k.SetConsoleCtrlHandler(None,True); assert k.GenerateConsoleCtrlEvent(0,0); time.sleep(.2)"
                        signaler=subprocess.run([sys.executable,'-c',script,str(process.pid)],capture_output=True,timeout=5)
                        self.assertEqual(signaler.returncode,0,signaler.stderr)
                    else:os.killpg(process.pid,signal.SIGINT)
                    stdout,stderr=process.communicate(timeout=10)
                    self.assertEqual(process.returncode,130,stderr)
                    self.assertEqual(stdout,b'')
                    records=[json.loads(line) for line in stderr.splitlines()]
                    self.assertEqual(len(records),1,stderr)
                    self.assertEqual((records[0]['kind'],records[0]['code']),('cancelled',None))
                    self.assertEqual(list(temporary.iterdir()),[], 'spec temp files leaked')
                finally:
                    tree.close()
                    if tree.process:
                        tree.process.stdout.close();tree.process.stderr.close()

    def test_startup_failure_and_handle_stability(self):
        with self.assertRaises(OSError):
            run_bounded(['zzy-nonexistent-executable'],cwd=ROOT,env=dict(os.environ))
        if os.name=='nt':
            from ctypes import wintypes as W
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.GetCurrentProcess.restype=W.HANDLE
            kernel.GetProcessHandleCount.argtypes=[W.HANDLE,ctypes.POINTER(W.DWORD)]
            def count():
                value=W.DWORD();self.assertTrue(kernel.GetProcessHandleCount(kernel.GetCurrentProcess(),ctypes.byref(value)));return value.value
            before=count()
            for _ in range(12):
                self.assertEqual(run_bounded([sys.executable,'-c','pass'],cwd=ROOT,env=dict(os.environ)),(0,b'',b''))
            self.assertLessEqual(count(),before+1)

    def test_job_setup_failure_reaps_suspended_child_and_closes_pipes(self):
        if os.name != 'nt':
            # POSIX start_new_session setup is owned by Popen, not a separate job.
            with self.assertRaises(OSError):
                run_bounded(['zzy-missing-command'],cwd=ROOT,env=dict(os.environ))
            return
        tree=ProcessTree()
        with patch.object(tree.job,'assign_and_resume',side_effect=OSError('setup failed')):
            with self.assertRaises(OSError):
                tree.start([sys.executable,'-c','import time;time.sleep(30)'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.assertIsNotNone(tree.process.poll())
        self.assertTrue(tree.process.stdout.closed);self.assertTrue(tree.process.stderr.closed)
        self.assertIsNone(tree.job.handle)
