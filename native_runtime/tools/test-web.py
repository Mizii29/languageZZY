"""Real loopback HTTP acceptance. Python is a test client, never a host dependency."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import http.client
import json
import os
from pathlib import Path
import queue
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "native_runtime/tests/web"
ROUTES = [
    ("GET", "/api/raw", "inspectRequest"), ("POST", "/api/echo", "echo"),
    ("POST", "/api/business", "business"), ("GET", "/api/mutate", "mutate"),
    ("GET", "/api/map", "mutateMap"), ("GET", "/api/machine", "moveGate"),
    ("POST", "/api/local", "local"), ("GET", "/api/unsupported", "unsupported"),
    ("GET", "/api/big", "big"), ("GET", "/api/status", "badStatus"),
    ("GET", "/api/cycle", "cycle"), ("POST", "/api/huge", "huge"),
    ("POST", "/api/rendezvous", "rendezvous"),
    ("GET", "/api/spin", "spin"),
]
SIGNAL = r"""
import ctypes, sys
k=ctypes.windll.kernel32
k.FreeConsole()
if not k.AttachConsole(int(sys.argv[1])): raise ctypes.WinError()
if not k.SetConsoleCtrlHandler(None, True): raise ctypes.WinError()
if not k.GenerateConsoleCtrlEvent(0, 0): raise ctypes.WinError()
"""


def signal(process):
    subprocess.run([sys.executable, "-c", SIGNAL, str(process.pid)], check=True,
                   capture_output=True, timeout=5)


def clean_env():
    return dict(os.environ, PATH="", PYTHONPATH="unusable-zzy-python-path")


def args_for(exe, source, routes):
    return [str(exe), str(source), *(
        part for method, path, handler in routes
        for part in ("--route", method, path, handler)
    )]


@contextmanager
def server(argv, cwd):
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen([*argv, "--port", "0"], cwd=cwd, stdout=subprocess.PIPE, stderr=errors,
                                text=True, encoding="utf-8", env=clean_env(), startupinfo=startup,
                                creationflags=subprocess.CREATE_NEW_CONSOLE)
        lines = queue.Queue()
        read = threading.Thread(target=lambda: lines.put(proc.stdout.readline()), daemon=True)
        read.start()
        line = ""
        try:
            line = lines.get(timeout=15)
            match = re.fullmatch(r"ZZY native web listening on http://127\.0\.0\.1:(\d+)\n", line)
            if not match:
                errors.seek(0)
                raise AssertionError(f"native listener failed: {line!r} {errors.read().decode('utf-8')}")
            yield int(match.group(1)), proc
        finally:
            try:
                if proc.poll() is None and line:
                    signal(proc)
                rc = proc.wait(timeout=8)
                errors.seek(0)
                if rc != 0:
                    raise AssertionError(f"service exit {rc}: {errors.read().decode('utf-8')}")
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=5)
                read.join(timeout=5)
                proc.stdout.close()


def request(port, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
    try:
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        return response.status, response.getheader("Content-Type"), response.read()
    finally:
        connection.close()


def post(port, path, body, headers=None):
    return request(port, "POST", path, body, headers or {"Content-Type": "application/json"})


def raw_request(port, raw):
    with socket.create_connection(("127.0.0.1", port), timeout=8) as sock:
        sock.sendall(raw)
        response = http.client.HTTPResponse(sock)
        response.begin()
        return response.status, response.getheader("Content-Type"), response.read()


def interim_headers(sock):
    headers = bytearray()
    while not headers.endswith(b"\r\n\r\n"):
        byte = sock.recv(1)
        if not byte or len(headers) >= 1024:
            raise AssertionError(f"incomplete interim response: {headers!r}")
        headers += byte
    return bytes(headers)


class NativeWeb(unittest.TestCase):
    exe: Path
    sqlite: bool

    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="ZZY Web 中文 ")
        self.addCleanup(directory.cleanup)
        self.cwd = Path(directory.name)
        for file in FIXTURE.iterdir():
            shutil.copyfile(file, self.cwd / file.name)
        self.marker = self.cwd / "started.txt"
        self.argv = args_for(self.exe, self.cwd / "app.zzy", ROUTES)
        self.contract = ["--contracts", str(self.cwd / "contracts.json")]
        self.valid = b'{"task":{"title":"task","id":9007199254740991},"tags":[1,true,null,{}],"extras":{"free":[1.0]}}'

    def check_json(self, result, status, expected):
        actual, mime, data = result
        self.assertEqual((actual, mime), (status, "application/json"), data)
        self.assertEqual(json.loads(data), expected)

    def code(self, result, status, code, **fields):
        self.check_json(result, status, {"error": {"code": code, **fields}})

    def cli(self, args):
        return subprocess.run(args, cwd=self.cwd, env=clean_env(), capture_output=True, timeout=10)

    def test_routes_json_and_recovery(self):
        demo = args_for(self.exe, ROOT / "examples/web/app.zzy",
                        [("GET", "/api/hello", "hello"), ("POST", "/api/greet", "greet")])
        with server([*demo, "--page", str(ROOT / "examples/web/index.html")], self.cwd) as (port, _):
            self.assertFalse(self.marker.exists())
            page = request(port, "GET", "/")
            self.assertEqual(page[:2], (200, "text/html; charset=utf-8"))
            self.assertIn(b"/api/hello", page[2])
            self.assertEqual(request(port, "HEAD", "/"), (200, page[1], b""))
            self.check_json(request(port, "GET", "/api/hello"), 200, {"message": "你好，ZZY Web！", "language": "ZZY"})
            self.check_json(post(port, "/api/greet", b'{"name":" ZZY "}'), 200, {"message": "你好，ZZY"})
        with server(self.argv, self.cwd) as (port, _):
            self.assertFalse(self.marker.exists())
            for path in ("/api/no", "/api/raw/", "/openapi.json"):
                self.code(request(port, "GET", path), 404, "not_found")
            self.code(request(port, "OPTIONS", "/api/raw"), 405, "method_not_allowed")
            self.assertEqual(request(port, "HEAD", "/api/raw")[0], 405)
            self.code(request(port, "GET", "/api/raw", b"x"), 400, "unexpected_body")
            self.code(post(port, "/api/echo", b"{}", {"Content-Type": "text/plain"}), 415, "unsupported_media_type")
            self.code(post(port, "/api/echo", b"{}", {"Content-Type": "application/json", "Content-Encoding": "gzip"}),
                      415, "unsupported_encoding")
            invalid = [b"", b"null true", b'{"x":1,"x":2}', b'"\\ud800"', b'"\xff"', b"NaN", b"1e999",
                       b"9007199254740992", b"-9007199254740992"]
            for body in invalid:
                with self.subTest(body=body):
                    self.code(post(port, "/api/echo", body), 400, "invalid_json")
            self.assertFalse(self.marker.exists())
            result = raw_request(port, b"GET /api/raw?x=1&y=+&x=1&=v&bad=%FF HTTP/1.1\r\n"
                                 b"Host: localhost\r\nX-Z: first\r\nX-A: mid\r\nx-z: \xe9\r\n\r\n")
            self.check_json(result, 200, {
                "method": "GET", "path": "/api/raw", "body": None,
                "query": [["x", "1"], ["y", " "], ["x", "1"], ["", "v"], ["bad", "\ufffd"]],
                "headers": [["host", "localhost"], ["x-z", "first"], ["x-a", "mid"], ["x-z", "\u00e9"]],
            })
            self.assertEqual(self.marker.read_text(encoding="utf-8"), "initialized")
            exact = b'[1,1.0,true,null,-9007199254740991,9007199254740991]'
            self.assertEqual(post(port, "/api/echo", exact)[2], exact)
            self.assertEqual(raw_request(port, b"POST /api/echo HTTP/1.1\r\nHost: localhost\r\n"
                                          b"Content-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n"
                                          b"3\r\n1.0\r\n0\r\n\r\n")[2], b"1.0")
            for path in ("unsupported", "big", "status", "cycle"):
                self.code(request(port, "GET", f"/api/{path}"), 500, "invalid_response")
            self.code(post(port, "/api/echo", b" " * 65536 + b"0"), 413, "body_too_large")
            self.check_json(post(port, "/api/echo", b" " * 65535 + b"0"), 200, 0)
            self.code(post(port, "/api/echo", b"[" * 65 + b"0" + b"]" * 65), 413, "resource_limit")
            self.code(post(port, "/api/huge", b'"' + b"x" * 34000 + b'"'), 503, "resource_limit")
            self.code(request(port, "GET", "/api/raw?" + "x" * 16400), 431, "metadata_too_large")
            self.check_json(post(port, "/api/echo", b"null"), 200, None)

    def test_contracts_both_modes_and_determinism(self):
        exported = self.cli([*self.argv, *self.contract, "--openapi"])
        self.assertEqual(exported.returncode, 0, exported.stderr)
        self.assertEqual(exported.stdout, self.cli([*self.argv, *self.contract, "--openapi"]).stdout)
        self.assertFalse(self.marker.exists())
        doc = json.loads(exported.stdout)
        self.assertEqual(doc["openapi"], "3.1.1")
        schemas = doc["components"]["schemas"]
        operation = doc["paths"]["/api/business"]["post"]
        ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[1]
        payload = schemas[ref]
        self.assertEqual(payload["required"], ["task", "tags", "extras"])
        self.assertFalse(payload["additionalProperties"])
        self.assertEqual(payload["properties"]["tags"]["items"], {})
        self.assertTrue(payload["properties"]["extras"]["additionalProperties"])
        child = schemas[payload["properties"]["task"]["$ref"].rsplit("/", 1)[1]]["properties"]
        self.assertEqual(child["ratio"], {"type": "number", "x-zzy-type": "Float", "default": -1.0})
        self.assertEqual(child["id"]["minimum"], -9007199254740991)
        self.assertIn("anyOf", operation["responses"]["500"]["content"]["application/json"]["schema"])
        for mode in ([], ["--shared"]):
            self.marker.unlink(missing_ok=True)
            with self.subTest(mode=mode), server([*self.argv, *self.contract, *mode], self.cwd) as (port, _):
                self.assertEqual(self.marker.exists(), bool(mode))
                self.marker.unlink(missing_ok=True)
                self.assertEqual(request(port, "GET", "/openapi.json")[2], exported.stdout.rstrip(b"\n"))
                for body, path, reason in (
                    (b'{}', "body.task", "missing"),
                    (self.valid.replace(b"9007199254740991", b"true"), "body.task.id", "type"),
                    (self.valid.replace(b"9007199254740991", b"1.0"), "body.task.id", "type"),
                    (self.valid.replace(b'"title":"task"', b'"title":null'), "body.task.title", "type"),
                    (self.valid.replace(b'"title":"task"', b'"title":"task","ratio":1'), "body.task.ratio", "type"),
                    (self.valid.replace(b'"title":"task"', b'"title":"task","f.x":1'), 'body.task["f.x"]', "unknown"),
                ):
                    self.code(post(port, "/api/business", body), 422, "contract_input", path=path, reason=reason)
                self.assertFalse(self.marker.exists())
                expected = {"task": {"title": "task", "id": 9007199254740991, "ratio": -1.0},
                            "tags": [1, True, None, {}], "extras": {"free": [1.0]}, "optional": None, "done": False}
                self.check_json(post(port, "/api/business", self.valid), 200, expected)
                self.assertEqual(self.marker.exists(), not bool(mode))
                self.check_json(post(port, "/api/business", self.valid.replace(b'"task","id"', b'"","id"')),
                                409, "title required")
                self.code(post(port, "/api/business", self.valid.replace(b'"task","id"', b'"bad output","id"')),
                          500, "contract_response", path="body.task", reason="missing")

    def test_startup_refusals(self):
        app = self.cwd / "app.zzy"
        source = app.read_text(encoding="utf-8")
        for declaration in (
            "(zyes) global := 1;", "(zno) deferred := (zzz)(1);", "(zno) alias := [data];",
            "(addnew) make() { (zyes) counter := 0; (return) (addnew)() => counter; }\n(zno) capture := make();",
        ):
            with self.subTest(declaration=declaration):
                app.write_text(source + "\n" + declaration, encoding="utf-8")
                result = self.cli([*self.argv, "--shared", "--port", "0"])
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(b"E303", result.stderr)
                self.assertFalse(result.stdout)
        for shape, diagnostic in (
            ("(shape) Bad { field; }", b"type annotation"),
            ("(shape) Bad { field: (Lazy); }", b"unsupported contract type"),
            ("(shape) Bad { field: Bad; }", b"recursive shape"),
            ("(shape) Bad { field: (Int) := 1 + 1; }", b"scalar literal"),
        ):
            self.marker.unlink(missing_ok=True)
            app.write_text(source + "\n" + shape, encoding="utf-8")
            (self.cwd / "contracts.json").write_text('{"POST /api/business":{"request":"Bad"}}', encoding="utf-8")
            result = self.cli([*self.argv, *self.contract, "--openapi"])
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn(diagnostic, result.stderr)
            self.assertFalse(self.marker.exists())

    def test_concurrent_requests_and_shared_freeze(self):
        for shared in (False, True):
            for path in self.cwd.glob("ready-*.txt"):
                path.unlink()
            flags = ["--shared"] if shared else []
            with self.subTest(shared=shared), server([*self.argv, *flags], self.cwd) as (port, _):
                with ThreadPoolExecutor(max_workers=4) as pool:
                    overlap = list(pool.map(lambda value: post(port, "/api/rendezvous", json.dumps(value).encode()), ["a", "b"]))
                    for expected, result in zip((["a"], ["b"]), overlap, strict=True):
                        self.check_json(result, 200, expected)
                    results = list(pool.map(lambda value: post(port, "/api/local", str(value).encode()), range(16)))
                for value, result in enumerate(results):
                    self.check_json(result, 200, [15, [value]])
                for route, expected in (("mutate", [7, 8, 9]), ("map", {"items": []}), ("machine", "opened")):
                    response = request(port, "GET", f"/api/{route}")
                    if shared:
                        self.code(response, 500, "zzy_error")
                    else:
                        self.check_json(response, 200, expected)
                self.check_json(post(port, "/api/local", b"42"), 200, [15, [42]])

    def test_deadlines_admission_disconnect_shutdown(self):
        with server([*self.argv, "--workers", "1", "--timeout-ms", "700"], self.cwd) as (port, proc):
            with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
                sock.sendall(b"POST /api/echo HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\n"
                             b"Content-Length: 50\r\nExpect: 100-continue\r\n\r\n")
                self.assertEqual(interim_headers(sock), b"HTTP/1.1 100 Continue\r\n\r\n")
                self.code(request(port, "GET", "/api/raw"), 503, "busy")
                for _ in range(4):
                    sock.sendall(b" ")
                    time.sleep(0.10)
                response = http.client.HTTPResponse(sock)
                response.begin()
                self.code((response.status, response.getheader("Content-Type"), response.read()), 408, "body_timeout")
            self.code(request(port, "GET", "/api/spin"), 504, "request_timeout")
            self.check_json(post(port, "/api/echo", b"7"), 200, 7)
            # A reset after initialization exercises cancellation while running.
            self.marker.unlink()
            with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
                sock.sendall(b"GET /api/spin HTTP/1.1\r\nHost: localhost\r\n\r\n")
                limit = time.monotonic() + 3
                while not self.marker.exists() and time.monotonic() < limit:
                    time.sleep(0.01)
                self.assertTrue(self.marker.exists())
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b"\x01\x00\x00\x00")
            limit = time.monotonic() + 0.45
            while True:
                response = post(port, "/api/echo", b"8")
                if response[0] != 503 or time.monotonic() >= limit:
                    break
                time.sleep(0.01)
            self.check_json(response, 200, 8)
            with socket.create_connection(("127.0.0.1", port), timeout=5) as stalled:
                stalled.sendall(b"POST /api/echo HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\n"
                                b"Content-Length: 50\r\nExpect: 100-continue\r\n\r\n")
                self.assertEqual(interim_headers(stalled), b"HTTP/1.1 100 Continue\r\n\r\n")
                signal(proc)
                self.assertEqual(proc.wait(timeout=5), 0)

    def test_sqlite_rollback_commit_and_restart(self):
        program = self.cwd / "sqlite.zzy"
        program.write_text("""
(shape) Response { status; body; }
(addnew) run(request) {
    (zno) value := data.get(request, "body");
    (addnew) work() {
        db.query("CREATE TABLE IF NOT EXISTS test (n INTEGER)", []);
        (zif?:) data.kind(value) == "int" { db.query("INSERT INTO test VALUES (?)", [value]); }
        (zif?:) value == -1 { (return) (T_T)("rollback"); }
        (zif?:) value == -2 { (while) (true) {} }
        (return) (^_^)(db.query("SELECT n FROM test ORDER BY n", []));
    }
    (?_?) db.transaction("native.sqlite3", work) {
        (^_^)(data) => { (return) Response::{status: 200, body: data}; }
        (T_T)(error) => { (return) Response::{status: 409, body: error}; }
    }
}
""", encoding="utf-8")
        argv = [*args_for(self.exe, program, [("POST", "/api/db", "run")]), "--timeout-ms", "750"]
        with server(argv, self.cwd) as (port, _):
            self.check_json(post(port, "/api/db", b"3"), 200, [[3]])
            self.check_json(post(port, "/api/db", b"-1"), 409, "rollback")
            self.code(post(port, "/api/db", b"-2"), 504, "request_timeout")
            self.check_json(post(port, "/api/db", b"null"), 200, [[3]])
        with server([*argv, "--shared"], self.cwd) as (port, _):
            self.check_json(post(port, "/api/db", b"null"), 200, [[3]])
            self.check_json(post(port, "/api/db", b"5"), 200, [[3], [5]])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--sqlite", choices=("ON", "OFF"), required=True)
    arguments = parser.parse_args()
    NativeWeb.exe = arguments.exe.resolve(strict=True)
    NativeWeb.sqlite = arguments.sqlite == "ON"
    tests = unittest.defaultTestLoader.getTestCaseNames(NativeWeb)
    if len(tests) != 6:
        raise SystemExit("native Web suite collection mismatch")
    if not NativeWeb.sqlite:
        tests.remove("test_sqlite_rollback_commit_and_restart")
        print("SQLite integration is not part of the explicitly SQLite-OFF build.", flush=True)
    suite = unittest.TestSuite(NativeWeb(name) for name in tests)
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not outcome.wasSuccessful() or bool(outcome.skipped))
