"""External-manifest runner; all language behavior goes through a subprocess."""

import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest

from tests.process import run_bounded
from zzy import __version__
from zzy.diagnostics import DiagnosticError
from zzy.resources import ResourcePolicy


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFESTS = tuple(ROOT / f"tests/{name}/cases.json" for name in ("lex", "run", "check", "p02", "p03", "p04", "p05", "p06", "e1", "e2", "e3"))


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _span(value):
    if (not isinstance(value, list) or len(value) != 4
            or any(type(n) is not int or n < 1 for n in value)
            or value[:2] > value[2:]):
        raise ValueError("span must be four ordered positive coordinates")


def load_cases(path):
    manifest = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    if (type(manifest) is not dict or set(manifest) != {"schema_version", "cases"}
            or type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1
            or not isinstance(manifest["cases"], list) or not manifest["cases"]):
        raise ValueError("invalid or empty manifest")
    cases = manifest["cases"]
    ids = set()
    required = {"id", "file", "mode", "cwd", "stdin", "timeout_seconds", "exit_code"}
    optional = {"stdout", "tokens", "diagnostic", "limits", "stdout_limit", "stderr_limit"}
    for case in cases:
        if (type(case) is not dict or not required <= case.keys()
                or case.keys() - required - optional):
            raise ValueError("invalid case fields")
        for key in ("id", "file", "mode", "cwd", "stdin"):
            if type(case[key]) is not str or (key != "stdin" and not case[key]):
                raise ValueError(f"invalid {key}")
        identity = (case["mode"], case["id"])
        if identity in ids:
            raise ValueError(f"duplicate case: {identity}")
        ids.add(identity)
        mode, status = case["mode"], case["exit_code"]
        if mode not in {"lex", "run", "check"}:
            raise ValueError("unknown mode")
        if type(status) is not int or status not in {0, 1, 2} or (mode != "run" and status == 1):
            raise ValueError("invalid exit_code for mode")
        timeout = case["timeout_seconds"]
        if type(timeout) not in {int, float} or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("invalid timeout_seconds")
        for key in ("stdout_limit", "stderr_limit"):
            if key in case and (type(case[key]) is not int or case[key] < 1):
                raise ValueError(f"invalid {key}")
        if "limits" in case and type(case["limits"]) is not dict:
            raise ValueError("limits must be an object")
        try:
            ResourcePolicy(case.get("limits", {}))
        except DiagnosticError as error:
            raise ValueError(error.diagnostic.message) from None
        if status == 0 and mode == "lex":
            tokens = case.get("tokens")
            if not isinstance(tokens, list) or not tokens:
                raise ValueError("lex success requires tokens including EOF")
            for token in tokens:
                if (not isinstance(token, list) or len(token) != 5
                        or any(type(token[i]) is not str for i in (0, 1))
                        or (token[2] is not None and type(token[2]) is not str)
                        or type(token[3]) is not bool):
                    raise ValueError("invalid token expectation")
                _span(token[4])
            if tokens[-1][0] != "EOF":
                raise ValueError("missing EOF expectation")
        elif type(case.get("stdout")) is not str:
            raise ValueError("case requires exact stdout")
        if status == 0:
            if "diagnostic" in case:
                raise ValueError("success cannot expect an error")
        else:
            diagnostic = case.get("diagnostic")
            if (type(diagnostic) is not dict or not {"code", "span"} <= diagnostic.keys()
                    or diagnostic.keys() - {"code", "span", "file", "message_contains", "notes"}
                    or not isinstance(diagnostic["code"], str)
                    or not re.fullmatch(r"E\d{3}", diagnostic["code"])):
                raise ValueError("failure requires a structured diagnostic")
            if "notes" in diagnostic and (not isinstance(diagnostic["notes"], list)
                    or not all(type(note) is str for note in diagnostic["notes"])):
                raise ValueError("invalid diagnostic notes")
            if diagnostic["span"] is not None:
                _span(diagnostic["span"])
            for key in ("file", "message_contains"):
                if key in diagnostic and not (type(diagnostic[key]) is str
                                             or (key == "file" and diagnostic[key] is None)):
                    raise ValueError(f"invalid diagnostic {key}")
    return sorted(cases, key=lambda case: (case["file"], case["mode"], case["id"]))


class BlackboxCase(unittest.TestCase):
    def __init__(self, case):
        super().__init__("runTest")
        self.case = case
        self.observed_status = None
        self.command = []

    def id(self):
        return self.case["mode"] + "_cli." + self.case["id"]

    def shortDescription(self):
        return self.id()

    def runTest(self):
        case = self.case
        self.command = [sys.executable, "-m", "zzy", case["mode"], case["file"],
                        "--diagnostic-format", "json"]
        with tempfile.TemporaryDirectory(prefix="ZZY blackbox 中文 ") as directory:
            if "limits" in case:
                config = Path(directory) / "limits.json"
                config.write_text(json.dumps({"policy_version": 1, "limits": case["limits"]}),
                                  encoding="utf-8")
                self.command.extend(("--limits", str(config)))
            status, stdout, stderr = run_bounded(
                self.command, cwd=ROOT / case["cwd"],
                env=dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="ascii"),
                timeout=case["timeout_seconds"], stdin=case["stdin"].encode("utf-8"),
                output_limit=case.get("stdout_limit", 1024**2),
                stderr_limit=case.get("stderr_limit", 1024**2),
            )
        self.observed_status = status
        self.assertEqual(status, case["exit_code"], stderr.decode("utf-8"))
        self.assertNotIn(b"Traceback", stderr)
        if case["mode"] == "lex" and status == 0:
            self.assertNotIn(b"\r\n", stdout)
            records = [json.loads(line) for line in stdout.decode("utf-8").splitlines()]
            expected = []
            for kind, lexeme, value, raw, coordinates in case["tokens"]:
                expected.append({"schema_version": 1, "kind": kind, "lexeme": lexeme,
                                 "value": value, "raw": raw, "span": self.span(coordinates)})
            self.assertEqual(records, expected)
        else:
            self.assertEqual(stdout.decode("utf-8"), case["stdout"])
        if status == 0:
            self.assertEqual(stderr, b"")
            return
        self.assertEqual(len(stderr.decode("utf-8").splitlines()), 1)
        record = json.loads(stderr)
        expected = case["diagnostic"]
        self.assertEqual(set(record), {"schema_version", "kind", "code", "file", "span", "message", "notes"})
        self.assertEqual((record["schema_version"], record["kind"]), (1, "error"))
        self.assertEqual(record["code"], expected["code"])
        self.assertEqual(record["file"], expected.get("file", case["file"]))
        self.assertEqual(record["span"], self.span(expected["span"]))
        self.assertIsInstance(record["message"], str)
        self.assertIsInstance(record["notes"], list)
        self.assertTrue(all(isinstance(note, str) for note in record["notes"]))
        if "notes" in expected:
            self.assertEqual(record["notes"], expected["notes"])
        if "message_contains" in expected:
            self.assertIn(expected["message_contains"], record["message"])

    @staticmethod
    def span(coordinates):
        if coordinates is None:
            return None
        a, b, c, d = coordinates
        return {"start": {"line": a, "column": b}, "end": {"line": c, "column": d}}


def suite(path):
    return unittest.TestSuite(BlackboxCase(case) for case in load_cases(path))


def main(argv=None):
    parser = argparse.ArgumentParser(description="ZZY lex/run/check external black-box tests (no spec)")
    parser.add_argument("manifests", nargs="*", type=Path)
    parser.add_argument("--report", type=Path, help="write commands, counts and effective resource policies as JSON")
    args = parser.parse_args(argv)
    try:
        cases = [case for path in sorted(args.manifests or DEFAULT_MANIFESTS) for case in load_cases(path)]
        identities = [(case["mode"], case["id"]) for case in cases]
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate case across manifests")
    except (OSError, ValueError, TypeError) as error:
        print(f"Collection failed: {error}", file=sys.stderr)
        return 1
    tests = [BlackboxCase(case) for case in cases]
    print(f"ZZY {__version__}; {len(tests)} external CLI cases; interpreter={sys.executable}", flush=True)
    try:
        result = unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(tests))
    except KeyboardInterrupt:
        print("Black-box run cancelled; not a passing result", file=sys.stderr)
        return 1
    passed = (bool(tests) and result.testsRun == len(tests) and result.wasSuccessful()
              and not result.skipped and all(test.observed_status is not None for test in tests))
    if not passed and result.wasSuccessful():
        print("Collection/execution incomplete or skipped; not a passing result", file=sys.stderr)
    if args.report:
        failures = {test.id(): details for test, details in result.errors + result.failures}
        records = []
        for test in tests:
            policy = ResourcePolicy(test.case.get("limits", {}))
            records.append({"id": test.id(), "command": test.command,
                            "case": test.case, "observed_exit_code": test.observed_status,
                            "passed": test.id() not in failures and test.observed_status is not None,
                            "failure": failures.get(test.id()),
                            "resource_policy": policy.effective_record(),
                            "resource_fingerprint": policy.fingerprint})
        try:
            args.report.write_text(json.dumps({"zzy_version": __version__, "tests_run": result.testsRun,
                                              "passed": passed, "cases": records},
                                             ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as error:
            print(f"Report failed: {error}", file=sys.stderr)
            return 1
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
