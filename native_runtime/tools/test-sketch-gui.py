"""Drive real HWNDs in the current Windows desktop. Python is only the client."""
import argparse
import ctypes as ct
from ctypes import wintypes as wt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


USER = ct.WinDLL("user32", use_last_error=True)
GDI = ct.WinDLL("gdi32", use_last_error=True)
KERNEL = ct.WinDLL("kernel32", use_last_error=True)
ENUM = ct.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
USER.EnumWindows.argtypes = (ENUM, wt.LPARAM)
USER.EnumWindows.restype = wt.BOOL
USER.GetWindowThreadProcessId.argtypes = (wt.HWND, ct.POINTER(wt.DWORD))
USER.GetWindowThreadProcessId.restype = wt.DWORD
USER.GetClassNameW.argtypes = (wt.HWND, wt.LPWSTR, ct.c_int)
USER.GetClassNameW.restype = ct.c_int
USER.GetWindowTextW.argtypes = (wt.HWND, wt.LPWSTR, ct.c_int)
USER.GetClientRect.argtypes = (wt.HWND, ct.POINTER(wt.RECT))
USER.GetWindowTextW.argtypes = (wt.HWND, wt.LPWSTR, ct.c_int)
USER.GetWindowTextW.restype = ct.c_int
USER.GetClassNameW.restype = ct.c_int
USER.PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
USER.PostMessageW.restype = wt.BOOL
USER.EnumChildWindows.argtypes = (wt.HWND, ENUM, wt.LPARAM)
USER.IsWindowVisible.argtypes = (wt.HWND,)
USER.SendMessageTimeoutW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM, wt.UINT, wt.UINT,
                                     ct.POINTER(ct.c_size_t))
USER.SendMessageTimeoutW.restype = wt.LPARAM
USER.GetDC.argtypes = (wt.HWND,)
USER.GetDC.restype = wt.HDC
USER.ReleaseDC.argtypes = (wt.HWND, wt.HDC)
USER.PrintWindow.argtypes = (wt.HWND, wt.HDC, wt.UINT)
GDI.CreateCompatibleDC.argtypes = (wt.HDC,)
GDI.CreateCompatibleDC.restype = wt.HDC
GDI.CreateCompatibleBitmap.argtypes = (wt.HDC, ct.c_int, ct.c_int)
GDI.CreateCompatibleBitmap.restype = wt.HBITMAP
GDI.SelectObject.argtypes = (wt.HDC, wt.HANDLE)
GDI.SelectObject.restype = wt.HANDLE
GDI.DeleteObject.argtypes = (wt.HANDLE,)
GDI.DeleteDC.argtypes = (wt.HDC,)
GDI.GetPixel.argtypes = (wt.HDC, ct.c_int, ct.c_int)
GDI.GetPixel.restype = wt.DWORD
KERNEL.OpenProcess.argtypes = (wt.DWORD, wt.BOOL, wt.DWORD)
KERNEL.OpenProcess.restype = wt.HANDLE
KERNEL.CloseHandle.argtypes = (wt.HANDLE,)
KERNEL.K32EnumProcessModules.argtypes = (wt.HANDLE, ct.POINTER(wt.HMODULE), wt.DWORD, ct.POINTER(wt.DWORD))
KERNEL.K32GetModuleFileNameExW.argtypes = (wt.HANDLE, wt.HMODULE, wt.LPWSTR, wt.DWORD)
SOURCE = '''(zno) c:=sketch.canvas(300,200,"真实窗口");
(zno) p:=sketch.pen(c,"p");
sketch.hide_cursor(p);
(addnew) click(x,y,b){io.print(b);sketch.dot(p,20);}
(addnew) drag(x,y,b){io.print("drag");}
(addnew) release(x,y,b){io.print("release");}
(addnew) key(k){io.print(k);}
(addnew) tick(){io.print("tick");sketch.cancel_timer(c,1);}
sketch.on_click(c,click);
sketch.on_drag(c,drag);
sketch.on_release(c,release);
sketch.on_key(c,key);
sketch.every(c,50::ms,tick);
io.print(sketch.show(c));
io.print(sketch.cancel_timer(c,1));
io.print(sketch.show(c));
sketch.save_svg(c,"sketch.svg");
io.print(sketch.save_project(c,"after.zzysketch"));
'''
SLOW = '''(zno) c:=sketch.canvas(120,100,"取消回调");
(addnew) slow(k){io.print("running");(while)(true){}}
sketch.on_key(c,slow);
io.print(sketch.show(c));
io.print("recovered");
'''
FAILURE = '''(zno) c:=sketch.canvas(120,100,"回调错误");
(addnew) nested(k){sketch.show(c);}
sketch.on_key(c,nested);
sketch.show(c);
'''


def await_value(probe, timeout=6):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = probe()
        if value:
            return value
        time.sleep(.015)
    raise AssertionError(f"timeout waiting for {probe}")


def window(pid, class_name="ZZYNativeSketchWindow"):
    matches = []

    @ENUM
    def find(hwnd, _):
        owner = wt.DWORD()
        USER.GetWindowThreadProcessId(hwnd, ct.byref(owner))
        label = ct.create_unicode_buffer(128)
        if owner.value == pid and USER.GetClassNameW(hwnd, label, len(label)):
            if label.value == class_name:
                matches.append(hwnd)
        return True

    USER.EnumWindows(find, 0)
    assert len(matches) <= 1
    return matches[0] if matches else None


def post(hwnd, message, value=0, data=0):
    assert USER.PostMessageW(hwnd, message, value, data), (hwnd, message, ct.get_last_error())


def title(hwnd):
    result = ct.create_unicode_buffer(512)
    USER.GetWindowTextW(hwnd, result, len(result))
    return result.value


def choose_path(dialog, path):
    value = ct.create_unicode_buffer(str(path))

    def set_filename():
        edits = []

        @ENUM
        def find(hwnd, _):
            label = ct.create_unicode_buffer(128)
            if USER.IsWindowVisible(hwnd) and USER.GetClassNameW(hwnd, label, len(label)) and label.value == "Edit":
                edits.append(hwnd)
            return True

        USER.EnumChildWindows(dialog, find, 0)
        if len(edits) != 1:
            return False
        result = ct.c_size_t()
        applied = ct.create_unicode_buffer(len(value))
        return (USER.SendMessageTimeoutW(edits[0], 0xC, 0, ct.addressof(value), 2, 500, ct.byref(result))
                and USER.SendMessageTimeoutW(edits[0], 0xD, len(applied), ct.addressof(applied), 2, 500, ct.byref(result))
                and applied.value == value.value)

    await_value(set_filename)
    post(dialog, 0x111, 1)  # IDOK


def modules(pid):
    handle = KERNEL.OpenProcess(0x410, False, pid)
    assert handle, ct.get_last_error()
    try:
        values, size = (wt.HMODULE * 512)(), wt.DWORD()
        assert KERNEL.K32EnumProcessModules(handle, values, ct.sizeof(values), ct.byref(size))
        assert 0 < size.value <= ct.sizeof(values)
        paths = []
        for index in range(size.value // ct.sizeof(wt.HMODULE)):
            path = ct.create_unicode_buffer(32768)
            assert KERNEL.K32GetModuleFileNameExW(handle, values[index], path, len(path))
            paths.append(path.value)
        names = {Path(p).name.lower() for p in paths}
        assert {"user32.dll", "gdi32.dll", "ole32.dll"} <= names, names
        assert not any(name.startswith(("python", "_tkinter", "tcl", "tk8")) for name in names)
        return paths
    finally:
        assert KERNEL.CloseHandle(handle)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    a = parser.parse_args()
    records = []
    if a.output and a.output.exists():
        raise FileExistsError(a.output)
    a.exe = a.exe.resolve()
    a.core = a.core.resolve()
    env = {**os.environ, "PATH": "", "PYTHONPATH": "invalid-native-gui"}
    with tempfile.TemporaryDirectory(prefix="ZZY 窗口 ") as directory:
        work = Path(directory)
        script = work / "scene.zzy"

        def session(name, source, actions, expected, status=0, code=None):
            script.write_text(source, encoding="utf-8")
            stdout = work / f"{name}.out"
            with stdout.open("wb") as sink:
                child = subprocess.Popen([a.exe, "run", script, "--gui", "--diagnostic-format", "json"],
                                         cwd=work, env=env, stdout=sink, stderr=subprocess.PIPE,
                                         creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    def find_visible():
                        if child.poll() is not None:
                            raise AssertionError((child.returncode, child.stderr.read().decode("utf-8")))
                        found = window(child.pid)
                        return found if found and title(found) else None

                    hwnd = await_value(find_visible)
                    assert USER.GetWindowThreadProcessId(hwnd, None)
                    loaded = modules(child.pid)
                    actions(hwnd, child, stdout)
                    _, stderr = child.communicate(timeout=6)
                    output = stdout.read_text(encoding="utf-8")
                    records.append(dict(id=name, exit_code=child.returncode, stdout=output,
                                        stderr=stderr.decode(), pid=child.pid, modules=loaded))
                    assert (child.returncode, output) == (status, expected), records[-1]
                    if code:
                        assert json.loads(stderr)["code"] == code, records[-1]
                    else:
                        assert not stderr, records[-1]
                    assert not window(child.pid)
                finally:
                    if child.poll() is None:
                        child.kill()
                    child.wait()

        def interaction(hwnd, child, stdout):
            assert "ZZY Sketch" in title(hwnd), repr(title(hwnd))
            await_value(lambda: "tick\n" in stdout.read_text(encoding="utf-8"))
            rect = wt.RECT()
            assert USER.GetClientRect(hwnd, ct.byref(rect))
            x, y = rect.right // 2, rect.bottom // 2
            xy = (y << 16) | x
            post(hwnd, 0x201, 1, xy)
            post(hwnd, 0x200, 1, xy + 15)
            post(hwnd, 0x202, 0, xy + 15)
            post(hwnd, 0x100, ord("X"))
            await_value(lambda: "x\n" in stdout.read_text(encoding="utf-8"))

            def black_center():
                dc = USER.GetDC(hwnd)
                memory = GDI.CreateCompatibleDC(dc)
                bitmap = GDI.CreateCompatibleBitmap(dc, rect.right, rect.bottom)
                old = GDI.SelectObject(memory, bitmap)
                try:
                    assert memory and bitmap and old
                    assert USER.PrintWindow(hwnd, memory, 1)
                    return GDI.GetPixel(memory, x, y) == 0 and GDI.GetPixel(memory, x + 40, y) == 0xFFFFFF
                finally:
                    GDI.SelectObject(memory, old)
                    GDI.DeleteObject(bitmap)
                    GDI.DeleteDC(memory)
                    USER.ReleaseDC(hwnd, dc)

            await_value(black_center)
            post(hwnd, 0x111, 111)  # Replay start.
            await_value(lambda: "0/1" in title(hwnd))
            post(hwnd, 0x111, 110)  # Single step.
            await_value(lambda: "1/1" in title(hwnd))
            post(hwnd, 0x111, 100)  # Undo after replay.
            await_value(lambda: "0 个对象" in title(hwnd))
            post(hwnd, 0x111, 101)
            await_value(lambda: "1 个对象" in title(hwnd))
            post(hwnd, 0x111, 113)  # Open the native SVG save dialog.
            modal = await_value(lambda: window(child.pid, "#32770"))
            post(modal, 0x10)
            await_value(lambda: not window(child.pid, "#32770"))
            assert not (work / "sketch.svg").exists()
            for menu, filename in ((113, "窗口导出.svg"), (114, "窗口项目.zzysketch")):
                post(hwnd, 0x111, menu)
                modal = await_value(lambda: window(child.pid, "#32770"))
                choose_path(modal, work / filename)
                await_value(lambda: not window(child.pid, "#32770"))
                await_value((work / filename).exists)
            assert '<circle cx="0"' in (work / "窗口导出.svg").read_text(encoding="utf-8")
            saved = json.loads((work / "窗口项目.zzysketch").read_text(encoding="utf-8"))
            assert saved["next_id"] == 2 and len(saved["objects"]) == 1
            post(hwnd, 0x111, 100)
            await_value(lambda: "0 个对象" in title(hwnd))
            post(hwnd, 0x111, 124)
            modal = await_value(lambda: window(child.pid, "#32770"))
            choose_path(modal, work / "窗口项目.zzysketch")
            await_value(lambda: "1 个对象" in title(hwnd))
            post(hwnd, 0x111, 101)  # Redo on loaded document must leave it unchanged.
            await_value(lambda: "1 个对象" in title(hwnd))
            post(hwnd, 0x111, 124)
            modal = await_value(lambda: window(child.pid, "#32770"))
            post(modal, 0x10)
            await_value(lambda: not window(child.pid, "#32770"))
            post(hwnd, 0x111, 101)  # Still viewing the loaded document.
            await_value(lambda: "1 个对象" in title(hwnd))
            # Closing the view returns to the script and its original canvas.
            post(hwnd, 0x10)
            second = await_value(lambda: (other if (other := window(child.pid)) != hwnd else None))
            post(second, 0x100, ord("X"))
            post(second, 0x10)

        session("input-timer-replay-two-windows", SOURCE, interaction,
                "tick\n1\ndrag\nrelease\nx\n(^_^)(null)\nfalse\n(^_^)(null)\n(^_^)(null)\n")
        project = json.loads((work / "after.zzysketch").read_text(encoding="utf-8"))
        assert "<circle" not in (work / "sketch.svg").read_text(encoding="utf-8")
        assert (project["next_id"], len(project["objects"])) == (2, 0)
        assert "timers" not in project and "callbacks" not in project

        def close_callback(hwnd, child, stdout):
            post(hwnd, 0x100, ord("X"))
            await_value(lambda: "running\n" in stdout.read_text(encoding="utf-8"))
            post(hwnd, 0x10)

        session("close-in-callback", SLOW, close_callback, "running\n(^_^)(null)\nrecovered\n")

        def overflow_callback(hwnd, child, stdout):
            post(hwnd, 0x100, ord("X"))
            await_value(lambda: "running\n" in stdout.read_text(encoding="utf-8"))
            for _ in range(4100):
                if child.poll() is not None:
                    break
                if not USER.PostMessageW(hwnd, 0x100, ord("X"), 0):
                    assert ct.get_last_error() == 1400  # HWND already destroyed by overflow cleanup.
                    break

        session("event-queue-overflow", SLOW, overflow_callback, "running\n", status=1, code="E211")
        session("recursive-show", FAILURE, lambda hwnd, *_: post(hwnd, 0x100, ord("X")), "", status=1, code="E214")
        script.write_text(SOURCE, encoding="utf-8")
        for exe in (a.core, a.exe):
            run = subprocess.run([exe, "check", script], cwd=work, env=env,
                                 capture_output=True, timeout=6, creationflags=subprocess.CREATE_NO_WINDOW)
            assert (run.returncode, run.stdout, run.stderr) == (0, b"", b"")
        assert len(records) == 4
    if a.output:
        a.output.write_text(json.dumps({"passed": True, "exe": str(a.exe),
                            "sha256": hashlib.sha256(a.exe.read_bytes()).hexdigest(),
                            "records": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Sketch native HWND: {len(records)}/{len(records)}")


if __name__ == "__main__":
    main()
