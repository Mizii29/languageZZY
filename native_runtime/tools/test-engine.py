"""Check the public native run engine modes against fixed behavior."""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    exe = parser.parse_args().exe.resolve()

    def invoke(*args):
        return subprocess.run([str(exe), "--diagnostic-format=json", *map(str, args)],
                              capture_output=True, encoding="utf-8", timeout=10)

    worker = """
(addnew) work(n) {
    (zyes) total := 0;
    (zyes) i := 0;
    (while) i < n { total <- total + i*i; i <- i+1; }
    (return) total;
}
"""
    cases = (
        ("order", worker + '(addnew) arg(){ io.print("arg"); (return) 10; }'
         'io.print(work(arg())); io.print(work(3));', 0, "arg\n285\n5\n", None),
        ("overflow", """
(addnew) big(n) {
    (zyes) i := 0;
    (while) i < 2 { n <- n+1; i <- i+1; }
    (return) n;
}
io.print(big(1152921504606846975));
""", 0, "1152921504606846977\n", None),
        ("diagnostic", """
(addnew) rem(n) { (return) 1%n; }
(addnew) work(n) {
    (zyes) i := 0;
    (while) i < 2 { i <- i+1; }
    (return) rem(n);
}
io.print("before"); io.print(work(0));
""", 1, "before\n", "E205"),
    )
    with tempfile.TemporaryDirectory(prefix="zzy-engine-") as directory:
        root = Path(directory)
        for name, program, status, stdout, code in cases:
            source = root / f"{name}.zzy"
            source.write_text(program, encoding="utf-8")
            results = [invoke("run", source, *options) for options in
                       ((), ("--engine", "ast"), ("--engine=auto",))]
            for result in results:
                assert (result.returncode, result.stdout) == (status, stdout), (name, result)
                if code is None:
                    assert not result.stderr, (name, result)
                else:
                    assert json.loads(result.stderr)["code"] == code, (name, result)
            assert len({result.stderr for result in results}) == 1, (name, results)

        source = root / "order.zzy"
        for args in (("run", source, "--engine"), ("run", source, "--engine=vm"),
                     ("check", source, "--engine=auto")):
            result = invoke(*args)
            assert result.returncode == 2 and not result.stdout, result
            assert json.loads(result.stderr)["code"] == "E401", result

        result = invoke("check", source)
        assert result.returncode == 0 and not result.stdout and not result.stderr, result
    print("native run engine: 13 invocations passed")


if __name__ == "__main__":
    main()
