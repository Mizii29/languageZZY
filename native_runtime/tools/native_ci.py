"""Native configure/build/CTest/install gate. Python orchestrates, never interprets ZZY."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]


def fingerprint_files(root, paths):
    records = {}
    for name in sorted(set(paths)):
        data = (root / name).read_bytes()
        # Normalize text checkouts, preserve byte-exact BOM/CRLF golden inputs.
        if (Path(name).suffix in (".cpp", ".hpp", ".h", ".cmake", ".py", ".ps1", ".md", ".yml")
                or Path(name).name == "CMakeLists.txt"):
            data = data.replace(b"\r\n", b"\n")
        records[name] = hashlib.sha256(data).hexdigest()
    digest = hashlib.sha256(json.dumps(records, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return dict(sha256=digest, files=records, text_normalization="LF for code/build/docs, fixtures verbatim")


def fingerprint():
    native = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others",
                                      "--exclude-standard", "--", "native_runtime",
                                      ".github/workflows/native-ci.yml"], cwd=ROOT).decode("utf-8").split("\0")
    fixtures = subprocess.check_output(["git", "ls-files", "-z", "--", "tests", "examples", "zzy",
                                        ".gitattributes", "pyproject.toml"], cwd=ROOT).decode("utf-8").split("\0")
    allowed = {".cpp", ".hpp", ".h", ".cmake", ".json", ".zzy", ".ps1", ".py", ".yml", ".yaml"}
    paths = [p for p in native + fixtures if p and (ROOT / p).is_file()
             and (Path(p).suffix in allowed or Path(p).name in ("CMakeLists.txt", "CMakePresets.json"))
             and not (p.startswith("native_runtime/tests/") and p.endswith("-report.md"))]
    return fingerprint_files(ROOT, paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--configuration", choices=("Debug", "Release"), default="Release")
    parser.add_argument("--fingerprint-only", action="store_true")
    parser.add_argument("--dumpbin", type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists(): parser.error("use a new evidence path")
    out.mkdir(parents=True)
    initial = fingerprint()
    (out / "source-fingerprint.json").write_text(json.dumps(initial, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.fingerprint_only: return 0
    config = args.configuration; preset = "native-" + config.lower(); build = ROOT / "build" / preset
    # Never downloads a toolchain or a C++ dependency. All source dependencies are vendored.
    env = dict(os.environ, PYTHONUTF8="1", HTTP_PROXY="http://127.0.0.1:9",
               HTTPS_PROXY="http://127.0.0.1:9", ALL_PROXY="http://127.0.0.1:9",
               CMAKE_POLICY_DEFAULT_CMP0170="NEW")
    records = []; started = time.monotonic(); passed = False

    def run(label, command):
        p = subprocess.run([str(v) for v in command], cwd=ROOT, env=env,
                           capture_output=True, encoding="utf-8", errors="replace", timeout=900)
        (out / (label + ".txt")).write_text(p.stdout + p.stderr, encoding="utf-8")
        records.append(dict(id=label, command=[str(v) for v in command], exit_code=p.returncode))
        if p.returncode: raise RuntimeError(f"{label} failed: see {out / (label + '.txt')}")
        return p.stdout

    report = dict(schema_version=1, configuration=config, platform=platform.platform(),
                  python_test_client=sys.version, python_runtime_dependency=False,
                  source_fingerprint=initial["sha256"], records=records,
                  network_scope="no dependency downloads; unusable proxies; adapter not disabled")
    try:
        run("configure", ["cmake", "--preset", preset, "-S", "native_runtime",
                         "-DZZY_NATIVE_WEB_TEST_PYTHON=" + sys.executable,
                         "-DFETCHCONTENT_FULLY_DISCONNECTED=ON"])
        run("build", ["cmake", "--build", build, "--config", config])
        listing = json.loads(run("ctest-inventory", ["ctest", "--test-dir", build, "-C", config, "--show-only=json-v1"]))
        names = [t["name"] for t in listing["tests"]]
        assert len(names) >= 83 and {"spec-process", "cli-boundaries", "native-ci-fingerprint"} <= set(names), names
        report["ctest_count"] = len(names)
        run("ctest", ["ctest", "--test-dir", build, "-C", config, "--output-on-failure",
                      "--no-tests=error", "--output-junit", out / "ctest.xml"])
        dumpbin = args.dumpbin
        if dumpbin is None:
            base = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Visual Studio"
            dumpbin = next(iter(sorted(base.glob("2022/*/VC/Tools/MSVC/*/bin/Hostx64/x64/dumpbin.exe"), reverse=True)), None)
        assert dumpbin and dumpbin.is_file(), "reviewed VS2022 dumpbin required"
        # Release only is publishable; Debug /MDd install is not a distribution.
        stage = Path(tempfile.mkdtemp(prefix="ZZY 发布 中文 空格 "))
        report["external_stage"] = str(stage)
        run("install", ["cmake", "--install", build, "--config", config, "--prefix", stage])
        artifacts = {}
        for executable in sorted((stage / "bin").glob("*.exe")):
            artifacts[executable.name] = hashlib.sha256(executable.read_bytes()).hexdigest()
            imports = run("imports-" + executable.stem, [dumpbin, "/dependents", executable])
            assert not any(s in imports.lower() for s in ("python", "pypy", "tcl", "tk8")), imports
        assert "zzy-native.exe" in artifacts
        report["artifacts"] = artifacts; report["dumpbin"] = str(dumpbin)
        exe = stage / "bin/zzy-native.exe"
        run("install-smoke", ["pwsh", "-NoProfile", "-File", ROOT / "native_runtime/tools/install-smoke.ps1",
                             "-Executable", exe, "-Output", out / "install-smoke.json"])
        run("installed-cli", [sys.executable, "-X", "utf8", ROOT / "native_runtime/tools/test-cli.py",
                              "--exe", exe, "--output", out / "installed-cli.json"])
        run("installed-spec", [sys.executable, "-X", "utf8", ROOT / "native_runtime/tools/test-spec.py",
                               "--exe", exe, "--output", out / "installed-spec.json"])
        report["publishable"] = config == "Release"
        assert initial == fingerprint(), "source changed while gate was running"
        passed = True
    finally:
        report.update(passed=passed, elapsed_seconds=time.monotonic()-started)
        (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("passed", "configuration", "ctest_count", "external_stage")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
