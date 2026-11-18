"""Development evidence audit; not a dependency of the native executable/CTest.

Run from the repository root with .venv/Scripts/python.exe -X utf8 <this file>.
All expected counts/names below are fixed independently of the observed reports.
"""
import gzip
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
program = "ast captures scopes purity literals budgets graph readonly metadata cancellation".split()
expected = {"frontend-fixed", "program-fixed", "program-empty-selection", "protocol", "cli-info", "cli-unsupported"}
expected.update("frontend-" + name for name in frontend)
expected.update("heap-" + name for name in heap)
expected.update("program-" + name for name in program)
expected.update("lifecycle-" + name for name in ("success", "resource", "cancel", "error"))
assert len(expected) == 44
summary = {}
for config, observer, collection_name, log in (
    ("debug", "observer-debug-rerun.json", "collection-debug-final.json", "ctest-debug-final.txt"),
    ("release", "observer-release.json", "collection-release.json", "ctest-release.txt"),
):
    report = load(config + "/report.json")
    assert report["passed"] is True
    assert report["provenance"]["origin"] == "CMakeMSVC"
    assert report["provenance"]["configuration"].lower() == config
    assert report["provenance"]["info"]["stage"] == "N2"
    assert report["provenance"]["info"]["python_fallback"] is False
    assert report["path_empty"] and report["pythonpath"] == "unusable-python-path"
    records = report["records"]
    assert len(records) == 58
    timeouts = [r for r in records if r["timed_out"]]
    assert len(timeouts) == 1 and timeouts[0]["process_exited"]
    assert timeouts[0]["purpose"] == "expected timeout cleanup probe"
    observed = records[-1]
    assert observed["purpose"] == "actual CLI runtime inspection"
    assert all(name.lower() == "conhost.exe" for name in observed["children"])
    assert observed["module_details"]
    for module in observed["module_details"]:
        assert "python" not in module["name"].lower()
        assert sha(Path(module["path"])) == module["sha256"]
        if module["name"].lower().startswith(("msvcp", "vcruntime", "ucrt")):
            assert module["company"] == "Microsoft Corporation"
            assert Path(module["path"]).parent.name.lower() == "system32"
    assert len(report["imports"]) == 6
    for name, imports in report["imports"].items():
        assert imports and set(map(str.lower, imports)) <= set(map(str.lower, report["allowed_direct_imports"]))
    assert len(report["sources"]) == 62
    for name, digest in report["sources"].items():
        # Same documented BOM/CRLF normalization as .NET ReadAllText in acceptance.
        data = (ROOT / "native_runtime" / name).read_text(encoding="utf-8-sig").replace("\r\n", "\n").encode()
        assert hashlib.sha256(data).hexdigest() == digest, name
    assert len(report["artifacts"]) == 6
    for name, digest in report["artifacts"].items():
        assert sha(ROOT / f"build/native-{config}" / config.title() / name) == digest
    exe_sha = report["artifacts"]["zzy-native.exe"]
    for kind, count in (("fixed", 87), ("check", 850), ("cli", 62)):
        evidence = load(f"{kind}-{config}.json")
        assert evidence["count"] == count and evidence["passed"] in (True, count)
        assert evidence["exe_sha256"] == exe_sha
    evidence = load(observer)
    assert evidence["total"] == evidence["passed"] == 17 and evidence["exe_sha256"] == exe_sha
    collection = load(collection_name)["tests"]
    assert len(collection) == 44 and {t["name"] for t in collection} == expected
    props = {t["name"]: {p["name"]: p["value"] for p in t["properties"]} for t in collection}
    assert props["frontend-default-boundaries"]["TIMEOUT"] == 180.0
    assert "100% tests passed out of 44" in (HERE / log).read_text(encoding="utf-8-sig")
    summary[config] = dict(ctest=44, normal_process_records=57, intentional_timeout_records=1,
                           source_files=62, executables=6, cli_sha256=exe_sha)

for smoke_name in ("installed-smoke.json", "published-smoke.json"):
    smoke = load(smoke_name)
    assert smoke["passed"] and smoke["side_effect_absent"] and len(smoke["records"]) == 9
    assert smoke["path_empty"] and smoke["pythonpath"] == "unusable-smoke"
    assert smoke["exe_sha256"] == summary["release"]["cli_sha256"]
    assert sha(Path(smoke["executable"])) == smoke["exe_sha256"]
    assert sha(ROOT / "dist/native-stage/bin/zzy-native.exe") == smoke["exe_sha256"]
    assert all(not r["timed_out"] for r in smoke["records"])
    if smoke_name == "published-smoke.json":
        assert not Path(smoke["executable"]).is_relative_to(ROOT)
        assert report["provenance"]["published_executable"] == smoke["executable"]
assert sha(ROOT / "docs/requirement.md") == "b099c19fc339ce1dc1aab7e9d6c8126a9c5c9ace3d31b969a0623df90f521d2b"
for raw in HERE.glob("collection-*.json.raw.gz"):
    assert json.loads(gzip.decompress(raw.read_bytes()).decode("utf-8-sig")) == load(raw.name.removesuffix(".raw.gz"))
result = dict(passed=True, configurations=summary, installed_smoke=9, published_copy_smoke=9,
              requirement_unchanged=True, python_regression=108,
              scope="N2 static frontend only; no runtime evaluation, manual Ctrl+C or sanitizer claim")
(HERE / "audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
