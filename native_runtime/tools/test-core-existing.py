"""Compare the native runtime with retained independent core CLI manifests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MANIFESTS = ("run", "p02", "p03", "p04", "p06")
# This is a frozen stage split, not a filter on what currently passes.
DEFERRED = {"p02-unimplemented-library": "array.sum belongs to N4-01"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    options = parser.parse_args()
    exe = options.exe.resolve(strict=True)
    if options.output.exists():
        parser.error("output already exists")
    cases = [(stage, case)
             for stage in MANIFESTS
             for case in json.loads((ROOT / "tests" / stage / "cases.json").read_text(encoding="utf-8"))["cases"]
             if case["mode"] == "run" and (stage != "p06" or case["id"].startswith("p06-resource-"))]
    if len(cases) != 550 or len({(stage, case["id"]) for stage, case in cases}) != len(cases):
        raise SystemExit("frozen core selection changed or is empty")
    records = []
    with tempfile.TemporaryDirectory(prefix="ZZY N3 core 中文 ") as folder:
        config = Path(folder) / "limits.json"
        for stage, case in cases:
            command = [str(exe), "run", case["file"], "--diagnostic-format", "json"]
            if "limits" in case:
                config.write_text(json.dumps({"policy_version": 1, "limits": case["limits"]}), encoding="utf-8")
                command.extend(["--limits", str(config)])
            record = {"stage": stage, "id": case["id"], "argv": command, "limits": case.get("limits", {}),
                      "source_sha256": hashlib.sha256((ROOT / case["cwd"] / case["file"]).read_bytes()).hexdigest()}
            records.append(record)
            try:
                result = subprocess.run(command, cwd=ROOT / case["cwd"], input=case["stdin"].encode("utf-8"),
                                        capture_output=True, timeout=case["timeout_seconds"],
                                        env=dict(os.environ, PATH="", PYTHONPATH="unusable-native-core"))
                out, err = result.stdout.decode("utf-8"), result.stderr.decode("utf-8")
                record.update(exit_code=result.returncode, stdout=out, stderr=err, timeout=False)
                diagnostic = case.get("diagnostic")
                if case["id"] in DEFERRED:
                    record["deferred"] = DEFERRED[case["id"]]
                    assert result.returncode == 1 and out == "" and json.loads(err)["code"] == "E402", "deferred capability"
                else:
                    assert result.returncode == case["exit_code"], "exit"
                    assert out == case["stdout"], "stdout"
                    if diagnostic is not None:
                        d = json.loads(err)
                        assert d["kind"] == "error" and d["code"] == diagnostic["code"], "diagnostic code"
                        assert d["schema_version"] == 1 and len(d) == 7, "diagnostic schema"
                        span = d["span"]
                        coords = [span[end][axis] for end in ("start", "end") for axis in ("line", "column")] if span else None
                        assert coords == diagnostic["span"], f"span: {coords} != {diagnostic['span']}"
                        if "file" in diagnostic:
                            assert d["file"] == diagnostic["file"], "file"
                        if "message_contains" in diagnostic:
                            assert diagnostic["message_contains"] in d["message"], "message"
                        if "notes" in diagnostic:
                            assert d["notes"] == diagnostic["notes"], "notes"
                    else:
                        for line in err.splitlines():
                            trace = json.loads(line)
                            assert trace["kind"] == "trace" and trace["code"] is None, "unexpected stderr"
                record["passed"] = True
            except subprocess.TimeoutExpired as error:
                record.update(timeout=True, failure=str(error), passed=False)
            except (AssertionError, ValueError) as error:
                record.update(failure=str(error), passed=False)
    passed = sum(r["passed"] and "deferred" not in r for r in records)
    report = {"schema_version": 1, "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
              "passed_core": passed, "deferred": len(DEFERRED), "records": records}
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for record in records:
        if not record["passed"]:
            print(record["id"], record["failure"], record.get("stderr", "")[:300])
    print(f"Existing core: {passed}/{len(cases) - len(DEFERRED)}, declared deferred: {len(DEFERRED)}")
    return int(not all(r["passed"] for r in records))


if __name__ == "__main__":
    raise SystemExit(main())
