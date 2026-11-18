"""Recheck evidence against current native sources and the actual MSVC binaries.

Development-only evidence audit, never a runtime or CTest dependency.
Run from the repository root: .venv/Scripts/python.exe -X utf8 <this file>
"""
import hashlib
import json
from pathlib import Path

ROOT = Path.cwd()
HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


frontend = "sha256 utf8 positions source-loader policy diagnostics lexer-boundaries default-boundaries source-defaults cancel-during-scan output cancellation-points".split()
heap = "array-cycle map-cycle closure-cycle reachable-alias quota-gc-retry atomic-limits allocation-rollback ownership cancellation unwind-roots iterative-graph repeated-collection".split()
expected = {"frontend-fixed", "protocol", "cli-info", "cli-unsupported"}
expected.update("frontend-" + case for case in frontend)
expected.update("heap-" + case for case in heap)
expected.update("lifecycle-" + case for case in ("success", "resource", "cancel", "error"))
assert len(expected) == 32
summary = {}
for config in ("debug", "release"):
    report = load(config + "/report.json")
    assert report["passed"] is True
    assert report["provenance"]["origin"] == "CMakeMSVC"
    assert report["provenance"]["configuration"].lower() == config
    records = report["records"]
    assert len(records) == 47
    timeouts = [r for r in records if r["timed_out"]]
    assert len(timeouts) == 1 and timeouts[0]["process_exited"]
    assert timeouts[0]["purpose"] == "expected timeout cleanup probe"
    # Windows' observed console helper is separately classified in acceptance.ps1.
    assert all(name.lower() == "conhost.exe" for name in records[-1]["children"])
    for module in records[-1]["module_details"]:
        assert "python" not in module["name"].lower()
        assert sha(Path(module["path"])) == module["sha256"]
        if module["name"].lower().startswith(("msvcp", "vcruntime", "ucrt")):
            assert module["company"] == "Microsoft Corporation"
            assert Path(module["path"]).parent.name.lower() == "system32"
    for name, imports in report["imports"].items():
        assert imports and set(map(str.lower, imports)) <= set(map(str.lower, report["allowed_direct_imports"]))
    for name, digest in report["sources"].items():
        # Match .NET ReadAllText: strip UTF-8 BOM and normalize CRLF, preserving content.
        data = (ROOT / "native_runtime" / name).read_text(encoding="utf-8-sig").replace("\r\n", "\n").encode()
        assert hashlib.sha256(data).hexdigest() == digest, name
    for name, digest in report["artifacts"].items():
        assert sha(ROOT / f"build/native-{config}" / config.title() / name) == digest
    exe_sha = report["artifacts"]["zzy-native.exe"]
    for kind, count in (("fixed", 87), ("frontend", 87), ("cli", 62)):
        evidence = load(f"{kind}-{config}.json")
        assert evidence["count"] == count and evidence["passed"] in (True, count)
        assert evidence["exe_sha256"] == exe_sha
    collection = load("collection-" + config + ".json")["tests"]
    assert len(collection) == 32 and {t["name"] for t in collection} == expected
    summary[config] = {"ctest": 32, "normal_process_records": 46, "intentional_timeout_records": 1,
                       "source_files": len(report["sources"]), "executables": len(report["artifacts"]), "cli_sha256": exe_sha}
for smoke_name in ("installed-smoke.json", "install-smoke.json"):
    smoke = load(smoke_name)
    assert smoke["passed"] and smoke["side_effect_absent"] and len(smoke["records"]) == 9
    assert smoke["exe_sha256"] == summary["release"]["cli_sha256"]
    assert sha(Path(smoke["executable"])) == smoke["exe_sha256"]
    assert sha(ROOT / "dist/native-stage/bin/zzy-native.exe") == smoke["exe_sha256"]
    if smoke_name == "install-smoke.json":
        assert not Path(smoke["executable"]).is_relative_to(ROOT)
assert sha(ROOT / "docs/requirement.md") == "b099c19fc339ce1dc1aab7e9d6c8126a9c5c9ace3d31b969a0623df90f521d2b"
result = {"passed": True, "configurations": summary, "installed_smoke": 9, "published_copy_smoke": 9, "requirement_unchanged": True}
(HERE / "audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
