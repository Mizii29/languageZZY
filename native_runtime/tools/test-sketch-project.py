"""Fixed results and bidirectional project/function interoperability."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
CREATE = '''(zno) canvas:=sketch.canvas(180,120,"中文");
(zno) p:=sketch.pen(canvas,"pen");
sketch.forward(p,20);
(zno) top:=sketch.add_layer(canvas,"top");
sketch.set_layer(p,top);
sketch.dot(p,10);
(zno) d:=sketch.capture(canvas);
sketch.translate_object(canvas,2,0,25);
sketch.undo(canvas);
sketch.frame_interval(canvas,1::ms / 2);
io.print(sketch.save_project(canvas,"drawing.zzysketch"));
io.print(sketch.save_function(d,"pattern.zzy","paint"));
'''
REOPEN = '''(use) "pattern.zzy" (as) art;
(addnew) reopen() -> (Result) {
    (zno) canvas:=sketch.load_project("drawing.zzysketch")?;
    io.print(sketch.pick(canvas,20,0));
    io.print(sketch.redo(canvas));
    io.print(sketch.pick(canvas,20,25));
    io.print(sketch.copy_object(canvas,2));
    io.print(art.paint(canvas,30,-10,1,90)?);
    io.print(sketch.pick(canvas,30,6));
    (return) sketch.save_project(canvas,"updated.zzysketch");
}
io.print(reopen());
'''
EXPECTED = "2\ntrue\n2\n3\n4\n4\n(^_^)(null)\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--python", type=Path)
    args = parser.parse_args()
    native = [str(args.exe.resolve())]
    reference = [str(args.python.resolve()), "-X", "utf8", "-m", "zzy"] if args.python else native
    with tempfile.TemporaryDirectory(prefix="ZZY 项目 ") as folder:
        work = Path(folder)
        (work / "create.zzy").write_text(CREATE, encoding="utf-8")
        (work / "reopen.zzy").write_text(REOPEN, encoding="utf-8")
        phases = 0

        def check(engine, mode, program, expected):
            nonlocal phases
            env = {**os.environ, "PATH": "", "PYTHONPATH": str(ROOT) if engine != native else "invalid"}
            actual = subprocess.run([*engine, mode, program], cwd=work, env=env,
                                    encoding="utf-8", capture_output=True, timeout=20)
            assert (actual.returncode, actual.stdout, actual.stderr) == (0, expected, ""), (
                engine, mode, program, actual.returncode, actual.stdout, actual.stderr
            )
            phases += 1

        check(native, "check", "create.zzy", "")
        assert not list(work.glob("*.zzysketch")) and not (work / "pattern.zzy").exists()
        for writer, reader in ((native, reference), (reference, native)):
            check(writer, "run", "create.zzy", "(^_^)(null)\n(^_^)(null)\n")
            data = json.loads((work / "drawing.zzysketch").read_text(encoding="utf-8"))
            assert (data["kind"], data["schema_version"], data["next_id"], data["interval_ms"]) == (
                "zzy-project", 1, 3, 1
            )
            assert [data["geometry"][idx]["id"] for idx in data["objects"]] == [1, 2]
            assert len(data["redo"]) == 1
            check(reader, "check", "reopen.zzy", "")
            assert not (work / "updated.zzysketch").exists()
            check(reader, "run", "reopen.zzy", EXPECTED)
            updated = json.loads((work / "updated.zzysketch").read_text(encoding="utf-8"))
            assert updated["next_id"] == 5 and not updated["redo"]
            assert [updated["geometry"][idx]["data"]["type"] for idx in updated["objects"]] == [
                "path", "dot", "dot", "group"
            ]
            (work / "updated.zzysketch").unlink()
        broken = json.loads(json.dumps(data))
        broken["redo"][0]["deltas"][0]["removed"][0][0] = 0
        malformed = json.loads(json.dumps(data))
        malformed["history"][0]["deltas"][0]["attrs"][0]["target"] = "layer:bad"
        for i, bad in enumerate((broken, malformed, {**data, "next_id": 2}, {**data, "extra": 1})):
            (work / f"bad{i}.zzysketch").write_text(json.dumps(bad), encoding="utf-8")
        (work / "reject.zzy").write_text(
            "".join(f'(?_?)sketch.load_project("bad{i}.zzysketch")'
                    '{(^_^)(c)=>{io.print("loaded");}(T_T)(m)=>{io.print("rejected");}}\n'
                    for i in range(4))
            + '(?_?)sketch.load_project("drawing.zzysketch"){(^_^)(c)=>{io.print("loaded");}(T_T)(m)=>{io.print("rejected");}}\n',
            encoding="utf-8",
        )
        check(native, "run", "reject.zzy", "rejected\n" * 4 + "loaded\n")
        assert not list(work.glob(".zzy-*.tmp"))
        assert phases == 8
        print(f"Sketch projects: {phases}/{phases}; Python peer: {bool(args.python)}")


if __name__ == "__main__":
    main()
