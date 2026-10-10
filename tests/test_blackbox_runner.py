import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.blackbox import ROOT, load_cases, main
from tests.process import run_bounded


class CaptureTests(unittest.TestCase):
    def test_capture_rejects_excess_and_timeout(self):
        for script, limit, timeout, error in (
            ("print('x' * 10000)", 16, 10, AssertionError),
            ("import time; time.sleep(30)", 1024, 0.1, subprocess.TimeoutExpired),
            # read1 must notice excess without waiting for 4096 bytes or EOF.
            ("import sys,time; sys.stdout.write('x'*32); sys.stdout.flush(); time.sleep(30)",
             16, 3, AssertionError),
        ):
            with self.subTest(script=script), self.assertRaises(error):
                run_bounded([sys.executable, "-c", script], cwd=ROOT, env=dict(os.environ),
                            output_limit=limit, timeout=timeout)

    def test_stderr_is_independently_bounded(self):
        with self.assertRaises(AssertionError):
            run_bounded([sys.executable, "-c", "import sys; sys.stderr.write('x'*100)"],
                        cwd=ROOT, env=dict(os.environ), output_limit=1000, stderr_limit=99)

    def test_parallel_pipes_stdin_and_exit_code(self):
        data = "中文😀\n".encode("utf-8")
        script = ("import sys; sys.stdout.buffer.write(sys.stdin.buffer.read()); "
                  "sys.stderr.buffer.write(b'e'*100000); "
                  "sys.stdout.buffer.write(b'o'*100000); sys.exit(7)")
        code, stdout, stderr = run_bounded([sys.executable, "-c", script], cwd=ROOT,
                                           env=dict(os.environ), stdin=data)
        self.assertEqual((code, stdout, stderr), (7, data + b"o"*100000, b"e"*100000))

    def test_timeout_process_and_readers_are_reaped(self):
        real_popen = subprocess.Popen
        processes = []

        def record(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            processes.append(process)
            return process

        with patch("tests.process.subprocess.Popen", side_effect=record):
            with self.assertRaises(subprocess.TimeoutExpired):
                run_bounded([sys.executable, "-c", "import time; time.sleep(30)"],
                            cwd=ROOT, env=dict(os.environ), timeout=0.1)
        self.assertIsNotNone(processes[0].poll())
        self.assertTrue(processes[0].stdout.closed)
        self.assertTrue(processes[0].stderr.closed)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ZZY runner ")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "cases.json"
        self.case = {"id": "probe", "file": "examples/hello.zzy", "mode": "run",
                     "cwd": ".", "stdin": "", "timeout_seconds": 10,
                     "exit_code": 0, "stdout": "5\n"}

    def write(self, cases):
        self.path.write_text(json.dumps({"schema_version": 1, "cases": cases}), encoding="utf-8")

    def run_manifest(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = main([str(self.path), *map(str, args)])
        return status, stdout.getvalue(), stderr.getvalue()

    def test_empty_duplicate_malformed_and_incomplete_manifests_fail(self):
        malformed = [[], [self.case, self.case], [dict(self.case, exit_code=True)],
                     [dict(self.case, mode="spec")], [dict(self.case, timeout_seconds=0)],
                     [dict(self.case, timeout_seconds=float("nan"))],
                     [dict(self.case, limits={"runtime_objects": False})],
                     [dict(self.case, stdout_limit=0)], [dict(self.case, extra=True)]]
        missing = dict(self.case)
        missing.pop("stdout")
        malformed.append([missing])
        for cases in malformed:
            with self.subTest(cases=cases):
                self.write(cases)
                self.assertEqual(self.run_manifest()[0], 1)
        for text in ('{"cases":', '{"schema_version":1,"schema_version":1,"cases":[]}', '[]'):
            self.path.write_text(text, encoding="utf-8")
            self.assertEqual(self.run_manifest()[0], 1)
        self.path.unlink()
        self.assertEqual(self.run_manifest()[0], 1)

    def test_real_mismatch_timeout_capture_and_startup_fail_suite(self):
        for changes in ({"stdout": "5"}, {"exit_code": 2, "diagnostic": {"code": "E103", "span": None}},
                        {"timeout_seconds": 0.000001}, {"stdout_limit": 1},
                        {"cwd": str(Path(self.temp.name) / "missing")}):
            with self.subTest(changes=changes):
                self.write([dict(self.case, **changes)])
                status, stdout, stderr = self.run_manifest()
                self.assertEqual(status, 1)
                self.assertIn("FAILED", stderr)

    def test_wrong_diagnostic_and_token_expectations_fail(self):
        case = copy.deepcopy(load_cases(ROOT / "tests/check/cases.json")[0])
        case.update(file="tests/check/inputs/diagnostic-name.zzy", exit_code=2,
                    diagnostic={"code": "E302", "span": [1,1,1,2]})
        self.write([case])
        self.assertEqual(self.run_manifest()[0], 1)
        lexical = next(c for c in load_cases(ROOT / "tests/lex/cases.json") if c["id"] == "basic")
        lexical["tokens"][0][0] = "WRONG"
        self.write([lexical])
        self.assertEqual(self.run_manifest()[0], 1)

    def test_success_report_and_cross_manifest_duplicates(self):
        self.write([self.case])
        report = Path(self.temp.name) / "report.json"
        self.assertEqual(self.run_manifest("--report", report)[0], 0)
        data = json.loads(report.read_text(encoding="utf-8"))
        self.assertTrue(data["passed"])
        self.assertEqual(data["tests_run"], 1)
        self.assertEqual(data["cases"][0]["observed_exit_code"], 0)
        self.assertEqual(len(data["cases"][0]["resource_fingerprint"]), 64)
        self.assertEqual(self.run_manifest(self.path)[0], 1)
        self.assertEqual(self.run_manifest("--report", report / "invalid.json")[0], 1)

    def test_subprocess_runner_exit_status(self):
        for cases, expected in (([self.case], 0), ([], 1), ([dict(self.case, stdout="wrong")], 1)):
            self.write(cases)
            result = subprocess.run([sys.executable, "-X", "utf8", "-m", "tests.blackbox", str(self.path)],
                                    cwd=ROOT, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, expected, result.stderr)
