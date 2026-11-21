"""Read lifetime counters from the exact child, before closing its handle."""
import ctypes as c
from ctypes import wintypes as w


class ProcessMemory(c.Structure):
    _fields_ = [('size', w.DWORD), ('faults', w.DWORD)] + [
        (key, c.c_size_t) for key in (
            'peak_working_set_bytes', 'working_set_bytes', 'peak_paged_pool',
            'paged_pool', 'peak_nonpaged_pool', 'nonpaged_pool', 'commit_bytes',
            'peak_private_bytes', 'private_bytes')
    ]


kernel = c.WinDLL('kernel32', use_last_error=True)
memory = kernel.K32GetProcessMemoryInfo
memory.argtypes = [w.HANDLE, c.POINTER(ProcessMemory), w.DWORD]
memory.restype = w.BOOL
times = kernel.GetProcessTimes
times.argtypes = [w.HANDLE] + [c.POINTER(w.FILETIME)] * 4
times.restype = w.BOOL


def counters(handle):
    values = ProcessMemory()
    values.size = c.sizeof(values)
    if not memory(handle, c.byref(values), values.size):
        raise c.WinError(c.get_last_error())
    stamps = [w.FILETIME() for _ in range(4)]
    if not times(handle, *(c.byref(stamp) for stamp in stamps)):
        raise c.WinError(c.get_last_error())
    system, user = [((s.dwHighDateTime << 32) | s.dwLowDateTime) * 100
                    for s in stamps[2:]]
    if not values.peak_working_set_bytes or not values.peak_private_bytes:
        raise RuntimeError('missing Windows lifetime memory peaks')
    return dict(cpu_user_ns=user, cpu_kernel_ns=system, cpu_ns=user+system,
                peak_working_set_bytes=values.peak_working_set_bytes,
                peak_private_bytes=values.peak_private_bytes)
