"""Cross-read campus and SQLite files with fixed answers for both writers and readers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.process import run_bounded


DATABASE = '''
(addnew) write() {
    db.query("CREATE TABLE IF NOT EXISTS task(id INTEGER PRIMARY KEY, title TEXT NOT NULL)", []);
    db.query("INSERT INTO task VALUES(?, ?)", [1, "作业"]);
    (return) (^_^)((null));
}
(addnew) abort() {
    db.query("INSERT INTO task VALUES(?, ?)", [2, "勿提交"]);
    (return) (T_T)("rollback");
}
io.print(db.transaction("任务.sqlite3", write));
io.print(db.transaction("任务.sqlite3", abort));
'''
READ_DATABASE = '''
(addnew) read() {
    (return) (^_^)(db.query("SELECT id, title FROM task ORDER BY id", []));
}
io.print(db.transaction("任务.sqlite3", read));
'''
CAMPUS_SAVE = '1\n2\n作业\n课程\n3\n1\n10\n任务.json\n1\n0\n'
CAMPUS_LOAD = '2\n任务.json\n1\n0\n'
CAMPUS_BYTES = ('{"schema_version":1,"next_id":2,"tasks":'
                '[{"id":1,"title":"作业","category":"课程","priority":3,"done":false}]}').encode()


def run_suite(exe, sqlite_enabled):
    expected_directions = [("native", "python"), ("python", "native")]
    subjects = {"native": [str(exe)], "python": [sys.executable, "-X", "utf8", "-m", "zzy"]}
    records = []

    def invoke(subject, folder, source, *, stdin="", limits=None):
        command = [*subjects[subject], "run", str(source), "--diagnostic-format", "json"]
        if limits:
            command.extend(("--limits", str(limits)))
        env = dict(os.environ, PATH="", PYTHONPATH=str(ROOT) if subject == "python" else "invalid-native")
        status, out, err = run_bounded(command, cwd=folder, env=env, stdin=stdin.encode(), timeout=30)
        assert (status, err) == (0, b""), (subject, source, status, err)
        return out.decode("utf-8")

    for writer, reader in expected_directions:
        with tempfile.TemporaryDirectory(prefix="ZZY N6 互读 ") as temporary:
            folder = Path(temporary)
            app = ROOT / "apps/zzy-campus"
            wrote = invoke(writer, folder, app / "main.zzy", stdin=CAMPUS_SAVE, limits=app / "limits.json")
            assert "保存成功\n任务数=1 next_id=2 未保存=false\n" in wrote, wrote
            target = folder / "任务.json"
            assert target.read_bytes() == CAMPUS_BYTES
            opened = invoke(reader, folder, app / "main.zzy", stdin=CAMPUS_LOAD, limits=app / "limits.json")
            assert "打开成功\n任务数=1 next_id=2 未保存=false\n" in opened, opened
            assert "id\ttitle\tcategory\tpriority\tdone\n1\t作业\t课程\t3\tfalse\n共1项\n" in opened
            assert target.read_bytes() == CAMPUS_BYTES and not list(folder.glob(".zzy-*.tmp"))
            records.append(dict(domain="campus", writer=writer, reader=reader, status="passed",
                                bytes_sha256=hashlib.sha256(CAMPUS_BYTES).hexdigest()))
            if not sqlite_enabled:
                records.append(dict(domain="sqlite", writer=writer, reader=reader, status="deferred",
                                    reason="explicit SQLite-OFF build"))
                continue
            create = folder / "write.zzy"
            read = folder / "read.zzy"
            create.write_text(DATABASE, encoding="utf-8")
            read.write_text(READ_DATABASE, encoding="utf-8")
            assert invoke(writer, folder, create) == "(^_^)(null)\n(T_T)(rollback)\n"
            assert invoke(reader, folder, read) == "(^_^)([[1, 作业]])\n"
            db = sqlite3.connect((folder / "任务.sqlite3").as_uri() + "?mode=ro", uri=True)
            try:
                assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
                assert db.execute("SELECT id,title FROM task ORDER BY id").fetchall() == [(1, "作业")]
            finally:
                db.close()
            assert not list(folder.glob("*.sqlite3-journal"))
            records.append(dict(domain="sqlite", writer=writer, reader=reader, status="passed",
                                rows=[[1, "作业"]]))
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--sqlite", choices=("ON", "OFF"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    records = run_suite(args.exe.resolve(strict=True), args.sqlite == "ON")
    counts = {"total": len(records), "applicable": sum(r["status"] != "deferred" for r in records),
              "passed": sum(r["status"] == "passed" for r in records), "failed": 0,
              "timed_out": 0, "deferred": sum(r["status"] == "deferred" for r in records)}
    report = dict(schema_version=1, counts=counts, records=records)
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
