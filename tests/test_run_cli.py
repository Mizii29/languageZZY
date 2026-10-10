"""Execute independent ZZY programs against hand-authored external expectations."""

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from tests.test_lexer_cli import ROOT, run_bounded


class RunCase(unittest.TestCase):
    def __init__(self, case):
        super().__init__("runTest")
        self.case = case

    def id(self):
        return "run_cli." + self.case["id"]

    def shortDescription(self):
        return self.id()

    def runTest(self):
        case = self.case
        command = [sys.executable, "-m", "zzy", "run", case["file"],
                   "--diagnostic-format", "json"]
        with tempfile.TemporaryDirectory(prefix="ZZY run 中文 ") as directory:
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
        self.assertEqual(stdout.decode("utf-8"), case["stdout"])
        self.assertNotIn(b"Traceback", stderr)
        if "diagnostic" not in case:
            self.assertEqual(stderr, b"")
            return
        self.assertEqual(len(stderr.decode("utf-8").splitlines()), 1)
        record = json.loads(stderr)
        expected = case["diagnostic"]
        self.assertEqual(set(record), {"schema_version", "kind", "code", "file", "span", "message", "notes"})
        self.assertEqual(record["schema_version"], 1)
        self.assertEqual(record["kind"], "error")
        self.assertEqual(record["code"], expected["code"])
        self.assertEqual(record["file"], expected.get("file", case["file"]))
        if expected["span"] is None:
            self.assertIsNone(record["span"])
        else:
            a, b, c, d = expected["span"]
            self.assertEqual(record["span"], {"start": {"line": a, "column": b},
                                             "end": {"line": c, "column": d}})
        if "message_contains" in expected:
            self.assertIn(expected["message_contains"], record["message"])


def load_tests(loader, standard_tests, pattern):
    manifest = json.loads((ROOT / "tests/run/cases.json").read_text(encoding="utf-8"))
    cases = manifest["cases"]
    if manifest["schema_version"] != 1 or not cases:
        raise ValueError("invalid or empty run manifest")
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("duplicate run case ID")
    return unittest.TestSuite(RunCase(case) for case in cases)


if __name__ == "__main__":
    unittest.main()
