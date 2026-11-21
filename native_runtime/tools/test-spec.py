"""Native spec fixed expectations and process isolation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import sys
from process_probe import K, tree, modules, wait_until


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    executable = args.exe.resolve()
    if args.output and args.output.exists(): parser.error("do not overwrite evidence")
    records = []
    cases = [
        ("empty", "io.print(\"bad\");", 1, (0, 0, 0, 0, 1)),
        ("pass", '(spec)"one"{(o_o)1==1;}', 0, (1, 1, 0, 0, 0)),
        ("failure", '(spec)"one"{(o_o)(false);}', 1, (1, 0, 1, 0, 0)),
        ("timeout", '(spec)"one"{(while)(true){}}', 1, (1, 0, 0, 1, 0)),
        ("isolation", '(zno)a:=[];(spec)"a"{array.push(a,1);io.write_text("private","x");}'
         '(spec)"b"{(o_o)len(a)==0;(?_?)io.read_text("private"){(^_^)(v)=>{(o_o)(false);}(T_T)(e)=>{}}}',
         0, (2, 2, 0, 0, 0)),
        ("collection", '(spec)"bad"{missing;}', 1, (0, 0, 0, 0, 1)),
        ("stdin-eof", '(spec)"a"{(o_o)io.input("")==(null);}(spec)"b"{(o_o)io.input("")==(null);}',
         0, (2, 2, 0, 0, 0)),
    ]
    with tempfile.TemporaryDirectory(prefix="ZZY spec 测试 ") as folder:
        path = Path(folder) / "测试.zzy"
        root = Path(folder); pool = root / "pool"; pool.mkdir()
        env = dict(os.environ, PATH="", PYTHONPATH="invalid", TEMP=str(pool), TMP=str(pool))
        for key in ("VIRTUAL_ENV", "PYTHONHOME", "CONDA_PREFIX"): env.pop(key, None)
        for name, code, expected, counts in cases:
            path.write_text(code, encoding="utf-8")
            actual = subprocess.run([executable, "test", path, "--timeout", ".2" if name == "timeout" else "8",
                                     "--diagnostic-format", "json"], cwd=folder,
                                    env=env, input="not shared",
                                    capture_output=True, encoding="utf-8", timeout=20)
            assert actual.returncode == expected, (name, actual)
            summary = json.loads(actual.stdout.splitlines()[-1])
            assert tuple(summary[k] for k in ("tests", "passed", "failed", "timed_out", "collection_errors")) == counts, (name, summary)
            for line in actual.stderr.splitlines():
                assert json.loads(line)["schema_version"] == 1
            records.append(dict(id=name, exit_code=actual.returncode, stdout=actual.stdout, stderr=actual.stderr))
            assert not list(pool.iterdir()), f"{name}: temporary files leaked: {list(pool.iterdir())}"
        assert not (Path(folder) / "private").exists()
        def run(name, code, counts, extra=(), target=None, text=False):
            path.write_text(code, encoding="utf-8")
            p = subprocess.run([executable, "test", target or path, "--timeout=8",
                                "--diagnostic-format", "text" if text else "json", *extra],
                               cwd=root, env=env, capture_output=True, timeout=20)
            record = dict(id=name, exit_code=p.returncode, stdout=p.stdout.decode(), stderr=p.stderr.decode())
            records.append(record)
            expected = 0 if counts[0] and counts[0] == counts[1] and not counts[4] else 1
            assert p.returncode == expected, record
            summary = json.loads(p.stdout.splitlines()[-1])
            assert tuple(summary[k] for k in ("tests","passed","failed","timed_out","collection_errors")) == counts, record
            if not text:
                for line in p.stderr.splitlines(): assert json.loads(line)["schema_version"] == 1, record
            assert not list(pool.iterdir())
            return record
        run("text-failure", '(spec)"one"{(o_o)(false);}', (1,0,1,0,0), text=True)
        (root / "limits.json").write_text('{"policy_version":1,"limits":{"stdout_bytes":128}}')
        run("output-excess", '(spec)"a"{io.print("'+"x"*150+'");}(spec)"b"{(o_o)(true);}',
            (2,1,1,0,0), ("--limits",str(root/"limits.json")))
        suite=root/"suite"; suite.mkdir(); marker=root/"never"
        (suite/"a.zzy").write_text('(spec)"a"{io.write_text("'+marker.as_posix()+'","bad");}')
        (suite/"b.zzy").write_text('(spec)"b"{unknown;}')
        run("collection-atomic","",(1,0,0,0,1),target=suite)
        assert not marker.exists()
        (suite/"a.zzy").write_text('(spec)"a"{io.print("A");}')
        (suite/"b.zzy").write_text('(spec)"b"{io.print("B");}')
        assert run("directory-order","",(2,2,0,0,0),target=suite)["stdout"].startswith("A\nB\n")
        path.write_text('io.print(io.input(""));',encoding="utf-8")
        for data,status,output in [("中文😀\r\n".encode(),0,"中文😀\n".encode()),(b"\xff\n",1,b"")]:
            p=subprocess.run([executable,"run",path,"--diagnostic-format=json"],
                             input=data,capture_output=True,cwd=root,env=env,timeout=8)
            assert (p.returncode,p.stdout)==(status,output),p
            records.append(dict(id="utf8-pipe",exit_code=p.returncode,stdout=p.stdout.decode(),stderr=p.stderr.decode()))
        ready=root/"ready"; go=root/"go"; dependency=root/"模块.zzy"
        dependency.write_text('(zyes) counter := 0; (addnew) next(){ counter <- counter + 1; (return) counter; }',encoding="utf-8")
        signal='io.write_text("'+ready.as_posix()+'","ready");'
        wait='(zyes) waiting := (true); (while) (waiting) { (?_?) io.read_text("'+go.as_posix()+'") { (^_^)(v) => { waiting <- (false); } (T_T)(e) => {} } }'
        path.write_text('(use)"模块.zzy"(as)m;(spec)"a"{'+signal+wait+
                        '(o_o)m.next()==1;}(spec)"b"{(o_o)m.next()==1;}',encoding="utf-8")
        process=subprocess.Popen([executable,"test",path,"--timeout=12","--diagnostic-format=json"],
                                 cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            try: wait_until(ready.exists)
            except AssertionError:
                stdout,stderr=process.communicate(timeout=3)
                raise AssertionError(f"snapshot worker did not reach ready: exit={process.returncode}, stdout={stdout!r}, stderr={stderr!r}")
            observed=wait_until(lambda:[r for r in tree() if r["parent"]==process.pid])
            assert all(r["name"].lower()==executable.name.lower() for r in observed),observed
            record=dict(id="snapshot-and-modules",parent_pid=process.pid,children=observed,
                        parent_modules=modules(process.pid),worker_modules=modules(observed[0]["pid"]))
            dependency.write_text("invalid changed source",encoding="utf-8"); go.write_text("go")
            stdout,stderr=process.communicate(timeout=15)
            assert process.returncode==0 and stderr==b"" and json.loads(stdout)["passed"]==2,(stdout,stderr)
            record.update(exit_code=process.returncode,stdout=stdout.decode()); records.append(record)
        finally:
            if process.poll() is None: process.kill(); process.wait()
            process.stdout.close(); process.stderr.close()
        assert not list(pool.iterdir())
        for mode in ("cancel-run","cancel-test","abnormal-worker","kill-parent"):
            ready.unlink(missing_ok=True); body=signal+'(while)(true){}'
            path.write_text(body if mode=="cancel-run" else '(spec)"wait"{'+body+'}(spec)"after"{(o_o)(true);}',encoding="utf-8")
            startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
            process=subprocess.Popen([executable,"run" if mode=="cancel-run" else "test",path,"--diagnostic-format=json"],
                cwd=root,env=env,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup,
                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            handle=None
            try:
                wait_until(ready.exists);children=[r for r in tree() if r["parent"]==process.pid]
                if mode!="cancel-run":
                    child=next(r for r in children if r["name"].lower()==executable.name.lower())
                    handle=K.OpenProcess(0x100001,False,child["pid"]);assert handle
                if mode.startswith("cancel"):
                    helper="import ctypes,sys,time; k=ctypes.WinDLL('kernel32'); k.FreeConsole(); assert k.AttachConsole(int(sys.argv[1])); assert k.SetConsoleCtrlHandler(None,True); assert k.GenerateConsoleCtrlEvent(0,0); time.sleep(.2)"
                    sent=subprocess.run([sys.executable,"-c",helper,str(process.pid)],capture_output=True,timeout=5)
                    assert sent.returncode==0,sent.stderr
                elif mode=="abnormal-worker": assert K.TerminateProcess(handle,0)
                else: process.kill()
                stdout,stderr=process.communicate(timeout=15)
                if mode.startswith("cancel"):
                    assert process.returncode==130 and not stdout,(process.returncode,stdout,stderr)
                    assert json.loads(stderr)["kind"]=="cancelled",stderr
                elif mode=="abnormal-worker":
                    assert process.returncode==1 and json.loads(stdout)["passed"]==1,(stdout,stderr)
                    assert "unexpectedly: 0" in stderr.decode(),stderr
                if handle: assert K.WaitForSingleObject(handle,5000)==0,"worker survived parent exit"
                records.append(dict(id=mode,parent_pid=process.pid,children=children,
                                    exit_code=process.returncode,stdout=stdout.decode(),stderr=stderr.decode()))
            finally:
                if process.poll() is None: process.kill();process.wait()
                if handle: K.CloseHandle(handle)
                process.stdout.close();process.stderr.close()
            if mode!="kill-parent": assert not list(pool.iterdir()),"normal/cancel temp cleanup"
        # Forced process termination cannot run temp destructors; outer test scope owns those paths.
        path.write_text('(spec)"recovered"{(o_o)(true);}',encoding="utf-8")
        p=subprocess.run([executable,"test",path],cwd=root,env=env,capture_output=True,timeout=12)
        assert p.returncode==0 and json.loads(p.stdout)["passed"]==1
        records.append(dict(id="recovery",exit_code=p.returncode))
    report=dict(schema_version=1,passed=True,count=len(records),executable=str(executable),
                exe_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),path_empty=True,
                pythonpath="invalid",virtual_env_removed=True,records=records)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Native spec/process: {len(records)}/{len(records)}")


if __name__ == "__main__":
    main()
