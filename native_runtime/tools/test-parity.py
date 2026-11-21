"""Run every retained external manifest against a backend and fixed expectations.

The manifest is the oracle. A Python process coordinates both backends, while the
native executable and the Python interpreter are tested as separate subjects.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.blackbox import DEFAULT_MANIFESTS, load_cases as load_manifest
from tests.process import run_bounded


def load_cases() -> list[dict]:
    cases = []
    identities = set()
    for path in DEFAULT_MANIFESTS:
        for case in load_manifest(path):
            identity = (case["mode"], case["id"])
            if identity in identities:
                raise ValueError(f"duplicate manifest case: {identity}")
            identities.add(identity)
            cases.append(case)
    if len(cases) != 1738:
        raise ValueError(f"frozen external manifest count changed: {len(cases)}")
    return sorted(cases, key=lambda item: (item["file"], item["mode"], item["id"]))


def span_value(value):
    if value is None:
        return None
    return {"start": {"line": value[0], "column": value[1]},
            "end": {"line": value[2], "column": value[3]}}


def compare(case, status, stdout, stderr):
    expected_status = case["exit_code"]
    if status != expected_status:
        return f"exit {status} != {expected_status}"
    if case["mode"] == "lex" and status == 0:
        if "\r\n" in stdout:
            return "lex output is not LF terminated"
        try:
            actual = [json.loads(line) for line in stdout.splitlines()]
        except json.JSONDecodeError as error:
            return f"invalid lex JSON: {error}"
        expected = [{"schema_version": 1, "kind": token[0], "lexeme": token[1],
                     "value": token[2], "raw": token[3], "span": span_value(token[4])}
                    for token in case["tokens"]]
        if actual != expected:
            return "lex output differs from fixed tokens"
    elif stdout != case.get("stdout", ""):
        return "stdout differs from fixed expectation"
    if status == 0:
        return "" if stderr == "" else "unexpected stderr"
    try:
        diagnostic = json.loads(stderr)
    except json.JSONDecodeError as error:
        return f"invalid diagnostic JSON: {error}"
    expected = case["diagnostic"]
    if set(diagnostic) != {"schema_version", "kind", "code", "file", "span", "message", "notes"}:
        return "diagnostic schema differs"
    if diagnostic["schema_version"] != 1 or diagnostic["kind"] != "error":
        return "diagnostic kind/schema differs"
    if diagnostic["code"] != expected["code"]:
        return f"diagnostic code {diagnostic['code']} != {expected['code']}"
    if diagnostic["span"] != span_value(expected.get("span")):
        return "diagnostic span differs"
    if diagnostic["file"] != expected.get("file", case["file"]):
        return "diagnostic file differs"
    if not isinstance(diagnostic["message"], str) or not isinstance(diagnostic["notes"], list) or not all(
            isinstance(note, str) for note in diagnostic["notes"]):
        return "diagnostic message or notes type differs"
    if "message_contains" in expected and expected["message_contains"] not in diagnostic["message"]:
        return "diagnostic message differs"
    if "notes" in expected and diagnostic["notes"] != expected["notes"]:
        return "diagnostic notes differ"
    return ""


def backend_command(kind, executable, case):
    source = case["file"]
    if kind == "native":
        return [str(executable), case["mode"], source, "--diagnostic-format", "json"]
    return [sys.executable, "-X", "utf8", "-m", "zzy", case["mode"], source,
            "--diagnostic-format", "json"]


def run_backend(kind, executable, cases, output):
    records = []
    counts = {"total": len(cases), "applicable": 0, "passed": 0, "failed": 0,
              "timed_out": 0, "deferred": 0}
    with tempfile.TemporaryDirectory(prefix=f"ZZY N6 {kind} 中文 ") as folder:
        config_folder = Path(folder)
        for index, case in enumerate(cases, 1):
            command = backend_command(kind, executable, case)
            if "limits" in case:
                config = config_folder / "limits.json"
                config.write_text(json.dumps({"policy_version": 1, "limits": case["limits"]}),
                                  encoding="utf-8")
                command += ["--limits", str(config)]
            env = dict(os.environ, PATH="", PYTHONPATH=str(ROOT) if kind == "python" else "invalid-native")
            started = time.monotonic()
            source = ROOT / case.get("cwd", ".") / case["file"]
            record = {"index": index, "id": case["id"], "mode": case["mode"],
                      "file": case["file"], "command": command,
                      "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()
                      if source.is_file() else None}
            counts["applicable"] += 1
            try:
                status, out, err = run_bounded(command, cwd=ROOT / case["cwd"], env=env,
                                               stdin=case["stdin"].encode("utf-8"),
                                               timeout=case["timeout_seconds"],
                                               output_limit=case.get("stdout_limit", 1024**2),
                                               stderr_limit=case.get("stderr_limit", 1024**2))
                stdout, stderr = out.decode("utf-8"), err.decode("utf-8")
                record.update(exit_code=status, stdout=stdout, stderr=stderr,
                              timeout=False, elapsed_seconds=time.monotonic() - started)
                failure = compare(case, status, stdout, stderr)
                if failure:
                    counts["failed"] += 1
                    record["failure"] = failure
                else:
                    counts["passed"] += 1
                    record["passed"] = True
            except subprocess.TimeoutExpired as error:
                counts["timed_out"] += 1
                record.update(timeout=True, passed=False, failure=str(error),
                              elapsed_seconds=time.monotonic() - started)
            except (OSError, ValueError, AssertionError) as error:
                counts["failed"] += 1
                record.update(timeout=False, passed=False, failure=str(error),
                              elapsed_seconds=time.monotonic() - started)
            records.append(record)
            if index % 100 == 0:
                print(f"{kind}: {index}/{len(cases)}", flush=True)
    report = {"schema_version": 1, "backend": kind,
              "exe_sha256": hashlib.sha256(executable.read_bytes()).hexdigest()
              if kind == "native" else None,
              "manifest_count": len(cases), "counts": counts, "records": records}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
    cases = load_cases()
    args.output.mkdir(parents=True, exist_ok=args.overwrite)
    reports = {}
    if args.backend in ("native", "both"):
        reports["native"] = run_backend("native", args.exe, cases, args.output / "native.json")
    if args.backend in ("python", "both"):
        reports["python"] = run_backend("python", args.exe, cases, args.output / "python.json")
    combined = {"schema_version": 1, "manifest_count": len(cases),
                "backends": {name: report["counts"] for name, report in reports.items()}}
    (args.output / "summary.json").write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n",
                                                 encoding="utf-8")
    for kind, report in reports.items():
        print(kind, report["counts"], flush=True)
    return 0 if all(r["counts"]["failed"] == 0 and r["counts"]["timed_out"] == 0
                    and r["counts"]["passed"] == r["counts"]["applicable"]
                    for r in reports.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
