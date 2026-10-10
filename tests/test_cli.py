import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from zzy.cli import main
from zzy.diagnostics import Cancelled
from zzy.source import SourceLoader


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ZZY 中文 空格 ")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.file = self.directory / "示例 空格.zzy"
        self.file.write_bytes(b"\xef\xbb\xbf" + "zzysay: 中😀\r\n".encode("utf-8"))

    def cli(self, *args, cwd=ROOT):
        env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="ascii")
        return subprocess.run([sys.executable, "-m", "zzy", *map(str, args)],
                              cwd=cwd, env=env, capture_output=True, timeout=10)

    def error(self, result, code="E401", exit_code=2):
        self.assertEqual(result.returncode, exit_code, result.stderr)
        self.assertEqual(result.stdout, b"")
        record = json.loads(result.stderr.decode("utf-8"))
        self.assertEqual(record["code"], code)
        self.assertNotIn(b"Traceback", result.stderr)
        return record

    def test_help_and_version(self):
        for args in (("--help",), ("source-info", "--help"), ("info", "--help"),
                     ("lex", "--help"), ("run", "--help"), ("check", "--help"), ("--version",)):
            result = self.cli(*args)
            self.assertEqual(result.returncode, 0)
            self.assertTrue(result.stdout.decode("utf-8"))
            self.assertEqual(result.stderr, b"")

    def test_info(self):
        result = self.cli("info")
        self.assertEqual(result.returncode, 0)
        record = json.loads(result.stdout)
        self.assertEqual(record["stage"], "P02")
        self.assertEqual(record["python_implementation"], "CPython")
        self.assertEqual(record["resource_policy"]["limits"]["numeric_digits"], 4096)

    def test_source_info_utf8_and_working_directory(self):
        result = self.cli("source-info", self.file.name, cwd=self.directory)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        record = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(record["file"], self.file.name)
        self.assertFalse(record["syntax_checked"])
        self.assertEqual(record["bytes"], len(self.file.read_bytes()))
        self.assertEqual(record["lines"], 2)
        self.assertNotIn(b"\r\n", result.stdout)

    def test_missing_file_and_invalid_utf8(self):
        for mode in ("source-info", "run", "check"):
            for name in ("missing.zzy", "bad.zzy"):
                (self.directory / "bad.zzy").write_bytes(b"\xff")
                record = self.error(self.cli(mode, name, "--diagnostic-format", "json", cwd=self.directory))
                self.assertEqual(record["file"], name)
                self.assertIsNone(record["span"])

    def test_run_check_cwd_options_and_literal_separator(self):
        file = self.directory / "-中文 空格.zzy"
        file.write_text('io.print("中😀");', encoding="utf-8")
        config = self.directory / "limits.json"
        config.write_text('{"policy_version":1,"limits":{"stdout_bytes":8}}', encoding="utf-8")
        for mode in ("run", "check"):
            for args in (("--limits", config.name, "--diagnostic-format=json", mode, "--", file.name),
                         (mode, "--limits", config.name, "--diagnostic-format=json", "--", file.name)):
                result = self.cli(*args, cwd=self.directory)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, b"")
                self.assertEqual(result.stdout, "中😀\n".encode("utf-8") if mode == "run" else b"")

    def test_check_never_constructs_interpreter(self):
        self.file.write_text('io.print(1 + "bad");', encoding="utf-8")
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with patch("zzy.cli.Interpreter", side_effect=AssertionError("check executed")) as execute:
                self.assertEqual(main(["check", str(self.file)]), 0)
                execute.assert_not_called()
        self.assertEqual((stdout.getvalue(), stderr.getvalue()), ("", ""))

    def test_run_check_frontend_diagnostics_match_in_both_formats(self):
        self.file.write_bytes(b"\xef\xbb\xbf" + 'io.print("😀");\r\n\tio.print(未声明);'.encode("utf-8"))
        for format in ("text", "json"):
            results = [self.cli(mode, self.file.name, "--diagnostic-format", format, cwd=self.directory)
                       for mode in ("run", "check")]
            self.assertEqual(results[0].stderr, results[1].stderr)
            for result in results:
                self.assertEqual((result.returncode, result.stdout), (2, b""))
                if format == "json":
                    record = json.loads(result.stderr)
                    self.assertEqual(record["span"], {"start": {"line": 2, "column": 11},
                                                     "end": {"line": 2, "column": 14}})
                else:
                    self.assertIn(f"{self.file.name}:2:11: E302".encode("utf-8"), result.stderr)

    def test_cli_errors_and_unimplemented_commands_fail(self):
        for args in ((), ("run",), ("check",), ("test", "tests"),
                     ("source-info",), ("--unknown",), ("info", "--diagnostic-format", "invalid")):
            record = self.error(self.cli(*args, "--diagnostic-format=json"))
            self.assertIsNone(record["file"])
            self.assertIsNone(record["span"])

    def test_options_before_and_after_command(self):
        config = self.directory / "limits.json"
        config.write_text('{"policy_version":1,"limits":{"source_file_bytes":1}}', encoding="utf-8")
        for args in (("--limits", config, "--diagnostic-format", "json", "source-info", self.file),
                     ("source-info", self.file, "--limits", config, "--diagnostic-format=json")):
            record = self.error(self.cli(*args), "E211")
            self.assertIn("source_file_bytes", record["message"])

    def test_bad_config_and_output_limit(self):
        config = self.directory / "limits.json"
        config.write_text('{"policy_version":true,"limits":{}}', encoding="utf-8")
        self.error(self.cli("info", "--limits", config, "--diagnostic-format=json"))
        config.write_text('{"policy_version":1,"limits":{"stdout_bytes":1,"stderr_bytes":1}}', encoding="utf-8")
        self.error(self.cli("info", "--limits", config, "--diagnostic-format=json"), "E211")

    def test_injected_cancellation_host_exhaustion_and_internal_bug(self):
        # Exercise the actual CLI exception boundary without requiring an interactive console.
        for failure, kind, code, status in (
            (KeyboardInterrupt(), "cancelled", None, 130),
            (Cancelled(), "cancelled", None, 130),
            (MemoryError(), "error", "E211", 2),
            (RecursionError(), "error", "E211", 2),
            (RuntimeError("injected defect"), "internal_error", None, 2),
        ):
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                with patch.object(SourceLoader, "read", side_effect=failure):
                    self.assertEqual(main(["source-info", str(self.file), "--diagnostic-format=json"]), status)
            record = json.loads(stderr.getvalue())
            self.assertEqual((record["kind"], record["code"]), (kind, code))
            self.assertEqual(stdout.getvalue(), "")
