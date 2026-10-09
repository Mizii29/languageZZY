"""Independent .zzy files and JSON expectations, exercised through the real CLI."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Event, Thread
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests/lex/cases.json"


def run_bounded(command, *, cwd, env, timeout=10, output_limit=1024**2):
    """The lex process executes no user code and spawns no child processes."""
    buffers = [bytearray(), bytearray()]
    exceeded = Event()
    read_errors = []
    with subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        def collect(stream, buffer):
            try:
                while chunk := stream.read(4096):
                    if len(buffer) + len(chunk) > output_limit:
                        exceeded.set()
                        process.kill()
                        return
                    buffer.extend(chunk)
            except Exception as error:
                read_errors.append(error)

        threads = [Thread(target=collect, args=(stream, buffer), daemon=True)
                   for stream, buffer in zip((process.stdout, process.stderr), buffers)]
        for thread in threads:
            thread.start()
        try:
            process.wait(timeout=timeout)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            for thread in threads:
                thread.join(timeout=5)
        if any(thread.is_alive() for thread in threads):
            raise AssertionError("CLI output reader did not stop")
        if read_errors:
            raise AssertionError(f"CLI output read failed: {read_errors}")
        if exceeded.is_set():
            raise AssertionError("CLI output exceeded capture limit; not a passing truncated result")
        return process.returncode, *(bytes(buffer) for buffer in buffers)


class LexCase(unittest.TestCase):
    def __init__(self, case):
        super().__init__("runTest")
        self.case = case

    def id(self):
        return "lex_cli." + self.case["id"]

    def shortDescription(self):
        return self.id()

    def runTest(self):
        case = self.case
        command = [sys.executable, "-m", "zzy", "lex", case["file"],
                   "--diagnostic-format", "json"]
        with tempfile.TemporaryDirectory(prefix="zzy-lex-") as directory:
            if "limits" in case:
                config = Path(directory) / "limits.json"
                config.write_text(json.dumps({"policy_version": 1, "limits": case["limits"]}),
                                  encoding="utf-8")
                command.extend(("--limits", str(config)))
            status, stdout, stderr = run_bounded(
                command, cwd=ROOT / case["cwd"],
                env=dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="ascii"),
                timeout=case["timeout_seconds"],
            )
        self.assertEqual(status, case["exit_code"], stderr.decode("utf-8"))
        self.assertNotIn(b"\r\n", stdout)
        self.assertNotIn(b"Traceback", stderr)
        if status == 0:
            self.assertEqual(stderr, b"")
            records = [json.loads(line) for line in stdout.decode("utf-8").splitlines()]
            expected = []
            for kind, lexeme, value, raw, coordinates in case["tokens"]:
                a, b, c, d = coordinates
                expected.append({"schema_version": 1, "kind": kind, "lexeme": lexeme,
                                 "value": value, "raw": raw,
                                 "span": {"start": {"line": a, "column": b},
                                          "end": {"line": c, "column": d}}})
            self.assertEqual(records, expected)
            self.assertEqual(records[-1]["kind"], "EOF")
        else:
            self.assertEqual(stdout, b"")
            self.assertEqual(len(stderr.decode("utf-8").splitlines()), 1)
            diagnostic = json.loads(stderr)
            expected = case["diagnostic"]
            self.assertEqual(diagnostic["schema_version"], 1)
            self.assertEqual(diagnostic["kind"], "error")
            self.assertEqual(diagnostic["code"], expected["code"])
            self.assertEqual(diagnostic["file"], expected.get("file", case["file"]))
            span = None
            if expected["span"] is not None:
                a, b, c, d = expected["span"]
                span = {"start": {"line": a, "column": b},
                        "end": {"line": c, "column": d}}
            self.assertEqual(diagnostic["span"], span)
            self.assertIsInstance(diagnostic["notes"], list)
            if "message_contains" in expected:
                self.assertIn(expected["message_contains"], diagnostic["message"])


class CaptureTests(unittest.TestCase):
    def test_capture_rejects_excess_and_timeout(self):
        env = dict(os.environ)
        for command, limit, timeout, exception in (
            ([sys.executable, "-c", "print('x' * 10000)"], 16, 10, AssertionError),
            ([sys.executable, "-c", "import time; time.sleep(30)"], 1024, 0.1,
             subprocess.TimeoutExpired),
        ):
            with self.assertRaises(exception):
                run_bounded(command, cwd=ROOT, env=env, output_limit=limit, timeout=timeout)


def load_tests(loader, standard_tests, pattern):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cases = manifest["cases"]
    if manifest["schema_version"] != 1 or not cases:
        raise ValueError("invalid or empty lexer manifest")
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("duplicate lexer case ID")
    suite = loader.loadTestsFromTestCase(CaptureTests)
    suite.addTests(LexCase(case) for case in cases)
    return suite


if __name__ == "__main__":
    unittest.main()
