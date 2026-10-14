"""Windows 8+ job ownership; loaded only on Windows.

Win32 references and the process/cancellation evidence are in tests/p06/README.md.
No BREAKAWAY flag: every ordinary descendant stays in this job.
"""
import ctypes as C
from threading import Lock
import time
from ctypes import wintypes as W


class BasicLimits(C.Structure):
    _fields_ = [("process_time", C.c_int64), ("job_time", C.c_int64),
                ("flags", W.DWORD), ("min_working_set", C.c_size_t),
                ("max_working_set", C.c_size_t), ("active_processes", W.DWORD),
                ("affinity", C.c_size_t), ("priority", W.DWORD), ("scheduling", W.DWORD)]


class ExtendedLimits(C.Structure):
    _fields_ = [("basic", BasicLimits), ("io", C.c_uint64 * 6),
                ("process_memory", C.c_size_t), ("job_memory", C.c_size_t),
                ("peak_process_memory", C.c_size_t), ("peak_job_memory", C.c_size_t)]


class Accounting(C.Structure):
    _fields_ = [("times", C.c_int64 * 4), ("faults", W.DWORD),
                ("total", W.DWORD), ("active", W.DWORD), ("terminated", W.DWORD)]


class ThreadEntry(C.Structure):
    _fields_ = [("size", W.DWORD), ("usage", W.DWORD), ("thread", W.DWORD),
                ("owner", W.DWORD), ("base_priority", W.LONG),
                ("delta_priority", W.LONG), ("flags", W.DWORD)]


kernel = C.WinDLL("kernel32", use_last_error=True)
for name, result, args in (
    ("CreateJobObjectW", W.HANDLE, [C.c_void_p, W.LPCWSTR]),
    ("SetInformationJobObject", W.BOOL, [W.HANDLE, C.c_int, C.c_void_p, W.DWORD]),
    ("AssignProcessToJobObject", W.BOOL, [W.HANDLE, W.HANDLE]),
    ("TerminateJobObject", W.BOOL, [W.HANDLE, W.UINT]),
    ("QueryInformationJobObject", W.BOOL, [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p]),
    ("CloseHandle", W.BOOL, [W.HANDLE]),
    ("CreateToolhelp32Snapshot", W.HANDLE, [W.DWORD, W.DWORD]),
    ("Thread32First", W.BOOL, [W.HANDLE, C.POINTER(ThreadEntry)]),
    ("Thread32Next", W.BOOL, [W.HANDLE, C.POINTER(ThreadEntry)]),
    ("OpenThread", W.HANDLE, [W.DWORD, W.BOOL, W.DWORD]),
    ("ResumeThread", W.DWORD, [W.HANDLE]),
):
    function = getattr(kernel, name)
    function.restype, function.argtypes = result, args


def checked(value):
    if not value:
        raise C.WinError(C.get_last_error())
    return value


class Job:
    def __init__(self):
        self.lock = Lock()
        self.handle = checked(kernel.CreateJobObjectW(None, None))
        try:
            limits = ExtendedLimits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            checked(kernel.SetInformationJobObject(self.handle, 9, C.byref(limits), C.sizeof(limits)))
        except BaseException:
            self.close()
            raise

    def assign_and_resume(self, process):
        checked(kernel.AssignProcessToJobObject(self.handle, int(process._handle)))
        # Popen closes the initial thread handle. Find the sole thread while the
        # process is still CREATE_SUSPENDED, then open only SUSPEND_RESUME access.
        snapshot = kernel.CreateToolhelp32Snapshot(4, 0)
        if snapshot == C.c_void_p(-1).value:
            raise C.WinError(C.get_last_error())
        try:
            entry = ThreadEntry()
            entry.size = C.sizeof(entry)
            present = kernel.Thread32First(snapshot, C.byref(entry))
            while present:
                if entry.owner == process.pid:
                    thread = checked(kernel.OpenThread(2, False, entry.thread))
                    try:
                        if kernel.ResumeThread(thread) == 0xFFFFFFFF:
                            raise C.WinError(C.get_last_error())
                        return
                    finally:
                        kernel.CloseHandle(thread)
                entry.size = C.sizeof(entry)
                present = kernel.Thread32Next(snapshot, C.byref(entry))
            raise OSError("suspended child thread was not found")
        finally:
            kernel.CloseHandle(snapshot)

    def terminate(self):
        with self.lock:
            if self.handle:
                checked(kernel.TerminateJobObject(self.handle, 1))

    def close(self):
        with self.lock:
            if self.handle:
                try:
                    checked(kernel.TerminateJobObject(self.handle, 1))
                    deadline = time.monotonic() + 5
                    while True:
                        accounting = Accounting()
                        checked(kernel.QueryInformationJobObject(self.handle, 1, C.byref(accounting), C.sizeof(accounting), None))
                        if accounting.active == 0:
                            break
                        if time.monotonic() >= deadline:
                            raise TimeoutError("job descendants did not terminate")
                        time.sleep(.01)
                finally:
                    checked(kernel.CloseHandle(self.handle))
                    self.handle = None
