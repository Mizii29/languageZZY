"""Collect before execution; each spec owns its process, cwd, input and limits."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .diagnostics import Diagnostic, DiagnosticError, Position, Span, Phase, display_path, ResourceExceeded
from .prepare import prepare
from .process import run_bounded
from .resources import ResourceMeter
from .source import SourceLoader


def run_specs(path, output, policy, timeout):
    output.meter.phase = Phase.EXECUTION
    target = Path(path)
    files = sorted(target.rglob("*.zzy")) if target.is_dir() else [target]
    jobs, collected_errors = [], 0
    collection = ResourceMeter(policy, Phase.FRONTEND)
    for file in files:
        try:
            meter = ResourceMeter(policy, Phase.FRONTEND)
            with SourceLoader(meter) as loader:
                source = loader.read(file)
                collection.consume("source_total_bytes", len(source.raw), file=display_path(file))
                collection.consume("module_count", 1, file=display_path(file))
                program = prepare(source, meter)
            specs = [node for node in program.root.children if node.kind == "spec"]
            for index, spec in enumerate(specs):
                jobs.append((source.path, source.raw, index, spec.data))
        except (DiagnosticError, ResourceExceeded) as error:
            output.failure(error.diagnostic)
            collected_errors += 1
    if not jobs and not collected_errors:
        output.failure(Diagnostic("没有收集到 spec", "E401"))
        collected_errors = 1
    passed = failed = timed_out = 0
    # A collection error prevents all initialization, including in valid files.
    if not collected_errors:
        for original, raw, index, name in jobs:
            with tempfile.TemporaryDirectory(prefix="ZZY spec ") as directory:
                root = Path(directory)
                snapshot, config = root / "snapshot.zzy", root / "limits.json"
                snapshot.write_bytes(raw)
                config.write_text(json.dumps({"policy_version": 1, "limits": dict(policy.limits)}), encoding="utf-8")
                env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]),
                           PYTHONIOENCODING="utf-8", TMP=directory, TEMP=directory)
                command = [sys.executable, "-X", "utf8", "-m", "zzy.spec_worker",
                           str(snapshot), str(original), str(index), str(config)]
                try:
                    status, stdout, stderr = run_bounded(command, cwd=root, env=env, timeout=timeout,
                        output_limit=policy.limits["stdout_bytes"], stderr_limit=policy.limits["stderr_bytes"]+4096)
                    output.write(stdout.decode("utf-8"))
                    for line in stderr.decode("utf-8").splitlines():
                        record = json.loads(line)
                        coordinates = record["span"]
                        span = Span(Position(**coordinates["start"]), Position(**coordinates["end"])) if coordinates else None
                        # Worker cwd is private; public paths remain relative to caller.
                        file = display_path(original) if record["file"] else None
                        diagnostic = Diagnostic(record["message"], record["code"], file, span,
                                                tuple(record["notes"]), record["kind"])
                        output.diagnostic(diagnostic)
                    if status == 0:
                        passed += 1
                    else:
                        failed += 1
                except subprocess.TimeoutExpired:
                    timed_out += 1
                    output.failure(Diagnostic(f"spec 超时：{name}", "E211", display_path(original)))
                except (OSError, UnicodeError, ValueError, AssertionError) as error:
                    failed += 1
                    output.failure(Diagnostic(f"spec 进程/输出失败：{name} ({type(error).__name__})", "E401", display_path(original)))
    summary = {"schema_version": 1, "tests": len(jobs), "passed": passed, "failed": failed,
               "timed_out": timed_out, "collection_errors": collected_errors}
    output.write(json.dumps(summary, ensure_ascii=False, separators=(",", ":")) + "\n")
    return 0 if jobs and passed == len(jobs) and not (failed or timed_out or collected_errors) else 1
