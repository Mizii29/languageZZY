"""Repeat paired AOT/C/CPython/ZZY measurements; retain every raw sample."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import sys
from time import perf_counter_ns

from experiments.aot.compile_int import compile_file
from zzy.resources import ResourcePolicy


ROOT = Path(__file__).resolve().parent
CASES = (("sum_squares", 10000), ("branch_calls", 1000))
LANGUAGES = ("aot", "c", "python", "zzy")
REPEATS = {
    "sum_squares": {"aot": 10000, "c": 10000, "python": 100, "zzy": 1},
    "branch_calls": {"aot": 100000, "c": 100000, "python": 1000, "zzy": 1},
}


def oracle(case, n):
    if case == "sum_squares":
        return n * (n - 1) * (2 * n - 1) // 6
    return n * (n - 1) // 2 + n % 2


def run_sample(language, case, n, binary, c_binary):
    repeat = REPEATS[case][language]
    if language == "aot":
        command = [str(binary), str(n), str(repeat)]
    elif language == "c":
        command = [str(c_binary), "sum" if case == "sum_squares" else "branch", str(n), str(repeat)]
    else:
        command = [sys.executable, "-X", "utf8", "-m", "experiments.aot.worker",
                   language, case, str(n), str(repeat)]
    started = perf_counter_ns()
    try:
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=35, check=False)
    except subprocess.TimeoutExpired as error:
        return {"status": "timeout", "command": command, "error": str(error),
                "wall_ns": perf_counter_ns() - started, "repeat": repeat}
    wall = perf_counter_ns() - started
    record = {"command": command, "returncode": completed.returncode,
              "wall_ns": wall, "repeat": repeat}
    if completed.returncode:
        return record | {"status": "error", "stderr": completed.stderr[-1500:]}
    try:
        if language in {"aot", "c"}:
            value, checksum = map(int, completed.stdout.strip().split())
            metrics = dict(line.split("=", 1) for line in completed.stderr.strip().splitlines())
            execute_ns = int(metrics["EXECUTE_NS"])
            peak = int(metrics["PEAK_WORKING_SET_BYTES"])
        else:
            data = json.loads(completed.stdout)
            value, checksum = data["value"], data["checksum"]
            execute_ns, peak = data["execute_ns"], data["peak_working_set_bytes"]
        expected = oracle(case, n)
        if value != expected or checksum != expected * repeat or execute_ns <= 0 or peak is None:
            raise AssertionError("answer, checksum or measurement is invalid")
    except (ValueError, KeyError, TypeError, AssertionError) as error:
        return record | {"status": "invalid", "stdout": completed.stdout[-1000:],
                         "stderr": completed.stderr[-1000:], "error": str(error)}
    return record | {"status": "ok", "value": value, "checksum": checksum,
                     "execute_ns": execute_ns, "execute_ns_per_call": execute_ns / repeat,
                     "peak_working_set_bytes": peak}


def summarize(raw, samples):
    summary = {}
    for case, n in CASES:
        for language in LANGUAGES:
            group = [row for row in raw if row["phase"] == "sample" and row["case"] == case
                     and row["language"] == language and row["status"] == "ok"]
            if len(group) != samples:
                raise AssertionError(f"missing samples: {case}/{language}: {len(group)}/{samples}")
            entry = {"n": n, "samples": samples, "repeat": REPEATS[case][language]}
            for metric in ("execute_ns_per_call", "wall_ns", "peak_working_set_bytes"):
                values = [row[metric] for row in group]
                median = statistics.median(values)
                entry[metric + "_median"] = median
                entry[metric + "_mad"] = statistics.median(abs(v - median) for v in values)
            summary[f"{case}/{language}"] = entry
    return summary


def measure(output, samples):
    if os.name != "nt":
        raise RuntimeError("this first memory probe requires Windows GetProcessMemoryInfo")
    if not 1 <= samples <= 100:
        raise ValueError("samples must be 1..100")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    compiler = shutil.which("gcc")
    if compiler is None:
        raise RuntimeError("GCC is required for the AOT pilot")
    environment = {"python": sys.version, "platform": platform.platform(),
                   "machine": platform.machine(),
                   "resource_fingerprint": ResourcePolicy().fingerprint,
                   "gcc": subprocess.run([compiler, "--version"], capture_output=True,
                                         text=True, check=True).stdout.splitlines()[0],
                   "samples_per_cell": samples, "warmups_per_cell": 3,
                   "timeout_seconds": 35, "native_compiler_flags": ["-O3", "-std=c11", "-Wall", "-Wextra", "-Werror"],
                   "repeats": REPEATS,
                   "sources_sha256": {path.name: sha256(path.read_bytes()).hexdigest()
                                      for path in (ROOT / "sum_squares.zzy", ROOT / "branch_calls.zzy",
                                                   ROOT / "reference.c", ROOT / "reference.py",
                                                   ROOT / "compile_int.py", ROOT / "measure.py", ROOT / "worker.py")}}
    (output / "environment.json").write_text(json.dumps(environment, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    binaries, compilation = {}, {}
    for case, _ in CASES:
        started = perf_counter_ns()
        _, binary = compile_file(ROOT / (case + ".zzy"), output / (case + ".exe"))
        compilation[case] = perf_counter_ns() - started
        binaries[case] = binary
    c_binary = output / "reference.exe"
    c_started = perf_counter_ns()
    built = subprocess.run([compiler, "-O3", "-std=c11", "-Wall", "-Wextra", "-Werror",
                            str(ROOT / "reference.c"), "-o", str(c_binary), "-lpsapi"],
                           capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
    if built.returncode:
        raise RuntimeError(f"C reference build failed: {built.stderr}")
    c_build_ns = perf_counter_ns() - c_started
    rng = random.Random(20261117)
    raw = []
    with (output / "raw.jsonl").open("w", encoding="utf-8", newline="\n") as sink:
        for phase, count in (("warmup", 3), ("sample", samples)):
            for round_index in range(count):
                cells = [(case, n, language) for case, n in CASES for language in LANGUAGES]
                rng.shuffle(cells)
                for case, n, language in cells:
                    record = {"phase": phase, "round": round_index, "case": case,
                              "n": n, "language": language} | run_sample(
                                  language, case, n, binaries[case], c_binary)
                    raw.append(record)
                    sink.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                    sink.flush()
                    if record["status"] != "ok":
                        raise RuntimeError(f"measurement failed: {case}/{language}/{phase}: {record}")
    result = {"aot_build_ns": compilation, "c_build_ns": c_build_ns,
              "cells": summarize(raw, samples),
              "raw_records": len(raw), "failures": sum(row["status"] != "ok" for row in raw)}
    (output / "summary.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=15)
    args = parser.parse_args(argv)
    result = measure(args.output, args.samples)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
