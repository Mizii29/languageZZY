"""Windows process evidence helpers; host test tooling, never imported by native runtime."""
import ctypes as ct
from ctypes import wintypes as wt
import time
from pathlib import Path

K = ct.WinDLL("kernel32", use_last_error=True)


class Entry(ct.Structure):
    _fields_ = [("size", wt.DWORD), ("usage", wt.DWORD), ("pid", wt.DWORD),
                ("heap", ct.c_size_t), ("module", wt.DWORD), ("threads", wt.DWORD),
                ("parent", wt.DWORD), ("priority", wt.LONG), ("flags", wt.DWORD),
                ("name", wt.WCHAR * 260)]


K.CreateToolhelp32Snapshot.argtypes = (wt.DWORD, wt.DWORD)
K.CreateToolhelp32Snapshot.restype = wt.HANDLE
K.Process32FirstW.argtypes = (wt.HANDLE, ct.POINTER(Entry))
K.Process32NextW.argtypes = (wt.HANDLE, ct.POINTER(Entry))
K.CloseHandle.argtypes = (wt.HANDLE,)
K.OpenProcess.argtypes = (wt.DWORD, wt.BOOL, wt.DWORD)
K.OpenProcess.restype = wt.HANDLE
K.WaitForSingleObject.argtypes = (wt.HANDLE, wt.DWORD)
K.TerminateProcess.argtypes = (wt.HANDLE, wt.UINT)
K.K32EnumProcessModules.argtypes = (wt.HANDLE, ct.POINTER(wt.HMODULE), wt.DWORD, ct.POINTER(wt.DWORD))
K.K32GetModuleFileNameExW.argtypes = (wt.HANDLE, wt.HMODULE, wt.LPWSTR, wt.DWORD)


def tree():
    handle = K.CreateToolhelp32Snapshot(2, 0)
    assert handle != wt.HANDLE(-1).value
    try:
        entry = Entry(); entry.size = ct.sizeof(entry)
        more = K.Process32FirstW(handle, ct.byref(entry))
        result = []
        while more:
            result.append(dict(pid=entry.pid, parent=entry.parent, name=entry.name))
            more = K.Process32NextW(handle, ct.byref(entry))
        return result
    finally:
        K.CloseHandle(handle)


def modules(pid):
    handle = K.OpenProcess(0x410, False, pid)
    assert handle, ct.get_last_error()
    try:
        values = (wt.HMODULE * 2048)(); size = wt.DWORD()
        assert K.K32EnumProcessModules(handle, values, ct.sizeof(values), ct.byref(size))
        assert size.value <= ct.sizeof(values)
        paths = []
        for i in range(size.value // ct.sizeof(wt.HMODULE)):
            path = ct.create_unicode_buffer(32768)
            assert K.K32GetModuleFileNameExW(handle, values[i], path, len(path))
            paths.append(path.value)
        assert not any(any(s in Path(p).name.lower() for s in ("python", "pypy", "tk8", "tcl8"))
                       for p in paths), paths
        return paths
    finally:
        K.CloseHandle(handle)


def wait_until(predicate, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(.01)
    raise AssertionError("probe deadline exceeded")
