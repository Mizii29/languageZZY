"""Run the campus application through native and Python CLI subjects.

Assertions and input programs come from the retained application tests. The
native subject only receives the common interpreter and host executable.
"""
from __future__ import annotations

import argparse
import ctypes as ct
import hashlib
import json
from pathlib import Path
import os
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.test_p09_app import CampusAppTests, MAIN, CONFIG, compact, document, task
from zzy.process import ProcessTree, run_bounded


METHODS = (
    "test_fixed_startup_eof_and_check",
    "test_real_menu_save_restart_and_exact_output",
    "test_crud_filter_sort_stats_and_export",
    "test_validation_matrix_fixed_independent_errors",
    "test_bad_json_encoding_missing_and_empty_files",
    "test_load_commit_is_all_or_nothing_and_success_resets_history",
    "test_history_alias_dirty_highwater_and_redo_branch",
    "test_history_99_100_101_and_empty_undo",
    "test_id_exhaustion_delete_save_and_restart",
    "test_menu_cancel_failed_save_blocks_load_and_eof_no_write",
    "test_open_retry_other_path_and_preserve_current",
    "test_every_draft_prompt_eof_is_non_mutating",
    "test_view_is_readonly_stable_empty_and_all_sort_modes",
    "test_save_revalidates_internal_state_before_touching_disk",
    "test_task_count_boundaries_real_cli",
    "test_application_file_byte_boundary_including_json_parse",
    "test_exhausted_menu_noop_cancel_and_failed_export",
    "test_numeric_errors_reenter_fields_and_cancel_preserve_id",
    "test_resource_failure_is_not_recoverable_format_error",
    "test_actual_ctrl_c_during_load_does_not_save_dirty_session",
    "test_windows_file_sharing_keeps_session_and_old_bytes",
)
SIGNAL = ("import ctypes,sys,time; k=ctypes.WinDLL('kernel32'); k.FreeConsole(); "
          "assert k.AttachConsole(int(sys.argv[1])); assert k.SetConsoleCtrlHandler(None,True); "
          "assert k.GenerateConsoleCtrlEvent(0,0); time.sleep(.2)")


class NativeCampusTests(CampusAppTests):
    subject = "native"
    executable: Path | None = None
    def invocation(self, source, mode):
        if self.subject == "python":
            command = [sys.executable, "-X", "utf8", "-m", "zzy", mode, str(source)]
            env = dict(os.environ, PYTHONPATH=str(ROOT))
        else:
            command = [str(self.executable), mode, str(source)]
            env = dict(os.environ, PATH="", PYTHONPATH="invalid-native-campus")
        command += ["--limits", str(CONFIG), "--diagnostic-format", "json"]
        return command, env

    def cli(self, source=MAIN, stdin="", mode="run", timeout=30):
        command, env = self.invocation(source, mode)
        return run_bounded(command, cwd=self.root, env=env, stdin=stdin.encode("utf-8"), timeout=timeout)

    def test_actual_ctrl_c_during_load_does_not_save_dirty_session(self):
        old = self.write_json("old.json", document([task()], 2))
        original = old.read_bytes()
        self.write_json("large.json", document([task(i+1, "x", "c", 1) for i in range(10000)], 10001))
        command, env = self.invocation(MAIN, "run")
        startup = subprocess.STARTUPINFO()
        startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        tree = ProcessTree()
        log = self.root / "out.txt"
        errors = self.root / "err.txt"
        with log.open("wb") as out, errors.open("wb") as err:
            try:
                proc = tree.start(command, cwd=self.root, env=env, stdin=subprocess.PIPE,
                                  stdout=out, stderr=err, startupinfo=startup,
                                  creationflags=subprocess.CREATE_NEW_CONSOLE)
                proc.stdin.write("2\nold.json\n3\n1\nchanged\nc\n1\n1\n11\n2\nlarge.json\n".encode())
                proc.stdin.flush()
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline and proc.poll() is None:
                    text = log.read_bytes()
                    if text.count("打开路径> ".encode()) == 2 and "未保存=true".encode() in text:
                        break
                    time.sleep(.01)
                else:
                    self.fail("application did not reach the dirty load prompt")
                sent = subprocess.run([sys.executable, "-c", SIGNAL, str(proc.pid)],
                                      capture_output=True, timeout=5)
                self.assertEqual(sent.returncode, 0, sent.stderr)
                self.assertEqual(proc.wait(timeout=10), 130)
            finally:
                tree.close()
                if tree.process and tree.process.stdin:
                    tree.process.stdin.close()
        diagnostic = json.loads(errors.read_bytes())
        self.assertEqual((diagnostic["kind"], diagnostic["code"]), ("cancelled", None))
        self.assertEqual(old.read_bytes(), original)
        self.assertEqual(list(self.root.glob(".zzy-*.tmp")), [])

    def test_windows_file_sharing_keeps_session_and_old_bytes(self):
        from ctypes import wintypes as wt

        old = self.write_json("locked.json", document([task()], 2))
        original = old.read_bytes()
        kernel = ct.WinDLL("kernel32", use_last_error=True)
        open_file = kernel.CreateFileW
        open_file.argtypes = (wt.LPCWSTR, wt.DWORD, wt.DWORD, wt.LPVOID, wt.DWORD, wt.DWORD, wt.HANDLE)
        open_file.restype = wt.HANDLE
        kernel.CloseHandle.argtypes = (wt.HANDLE,)
        # Hold existing file without sharing read, write or delete access.
        handle = open_file(str(old), 0x80000000, 0, None, 3, 0, None)
        self.assertNotEqual(handle, wt.HANDLE(-1).value, ct.get_last_error())
        try:
            out = self.run_ok(stdin="1\n2\nnew\nc\n1\n1\n10\nlocked.json\n1\n11\n2\nlocked.json\n0\n1\n")
            self.assertIn("I/O failed:", out)
            self.assertIn("打开失败：", out)
            self.assertIn("1\tnew\tc\t1\tfalse\n", out)
            self.assertIn("有未保存修改", out)
        finally:
            kernel.CloseHandle(handle)
        self.assertEqual(old.read_bytes(), original)
        self.assertEqual(list(self.root.glob(".zzy-*.tmp")), [])


def run_subject(subject, executable, output):
    NativeCampusTests.subject = subject
    NativeCampusTests.executable = executable
    records = []
    for name in METHODS:
        started = time.monotonic()
        result = unittest.TestResult()
        NativeCampusTests(name).run(result)
        errors = result.failures + result.errors + result.skipped
        details = [dict(test=test.id(), detail=detail) for test, detail in errors]
        status = "passed" if not errors else "failed"
        if any("subprocess.TimeoutExpired:" in item["detail"] for item in details):
            status = "timed_out"
        records.append(dict(id=name, status=status, seconds=round(time.monotonic()-started, 3), errors=details))
        if errors:
            print(f"{subject} {name}: {status}", flush=True)
    report = {
        "backend": subject,
        "total": len(records),
        "applicable": len(records),
        "passed": sum(r["status"] == "passed" for r in records),
        "failed": sum(r["status"] == "failed" for r in records),
        "timed_out": sum(r["status"] == "timed_out" for r in records),
        "deferred": 0,
        "exe_sha256": hashlib.sha256(executable.read_bytes()).hexdigest() if subject == "native" else None,
        "sources": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(MAIN.parent.glob("*.zzy"))},
        "records": records,
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"campus {subject}: {report['passed']}/{report['total']}")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--backend", choices=("native", "python", "both"), default="both")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.output.exists() and not args.overwrite:
        parser.error("choose a new evidence path")
    args.exe = args.exe.resolve(strict=True)
    args.output.mkdir(parents=True, exist_ok=args.overwrite)
    reports = {}
    if args.backend in ("native", "both"):
        reports["native"] = run_subject("native", args.exe, args.output / "native.json")
    if args.backend in ("python", "both"):
        reports["python"] = run_subject("python", args.exe, args.output / "python.json")
    (args.output / "summary.json").write_text(json.dumps({"schema_version": 1, "backends": reports},
                                                           ensure_ascii=False, indent=2) + "\n",
                                                    encoding="utf-8")
    return 0 if all(report["applicable"] == report["passed"] for report in reports.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
