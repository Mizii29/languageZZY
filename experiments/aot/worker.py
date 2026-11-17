"""Separate-process ZZY/CPython execution and Windows peak-memory probe."""

import argparse
import ctypes
import json
from pathlib import Path
import sys
from time import perf_counter_ns

from experiments.aot import reference


ROOT = Path(__file__).resolve().parent


def peak_working_set_bytes():
    if sys.platform != "win32":
        return None

    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_uint32), ("page_fault_count", ctypes.c_uint32),
                    ("peak_working_set_size", ctypes.c_size_t),
                    ("working_set_size", ctypes.c_size_t),
                    ("quota_peak_paged_pool_usage", ctypes.c_size_t),
                    ("quota_paged_pool_usage", ctypes.c_size_t),
                    ("quota_peak_non_paged_pool_usage", ctypes.c_size_t),
                    ("quota_non_paged_pool_usage", ctypes.c_size_t),
                    ("pagefile_usage", ctypes.c_size_t),
                    ("peak_pagefile_usage", ctypes.c_size_t)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_uint32]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    data = Counters()
    data.cb = ctypes.sizeof(data)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(data), data.cb):
        raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")
    return data.peak_working_set_size


def measure(language, case, n, repeat):
    if language == "python":
        function = getattr(reference, case)
        started = perf_counter_ns()
        values = [function(n) for _ in range(repeat)]
        elapsed = perf_counter_ns() - started
    else:
        from zzy.embedding import load_module

        with load_module(ROOT / (case + ".zzy")) as module:
            started = perf_counter_ns()
            values = [module.call("bench", n).value for _ in range(repeat)]
            elapsed = perf_counter_ns() - started
    if not values or any(value != values[0] for value in values):
        raise AssertionError("inconsistent repeated results")
    return {"value": values[0], "checksum": sum(values), "execute_ns": elapsed,
            "repeat": repeat, "peak_working_set_bytes": peak_working_set_bytes()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("language", choices=("zzy", "python"))
    parser.add_argument("case", choices=("sum_squares", "branch_calls"))
    parser.add_argument("n", type=int)
    parser.add_argument("repeat", type=int)
    args = parser.parse_args(argv)
    if not 1 <= args.repeat <= 100000:
        parser.error("repeat must be 1..100000")
    print(json.dumps(measure(args.language, args.case, args.n, args.repeat),
                     separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
