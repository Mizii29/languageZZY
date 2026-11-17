"""Explicit GCC-only tests for the optional compiler pilot."""

from contextlib import redirect_stdout
import io
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from experiments.aot.compile_int import Unsupported, compile_file, render_file
from zzy.embedding import load_module


ROOT = Path(__file__).resolve().parent


class AotPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = TemporaryDirectory()
        cls.outputs = {}
        for name in ("sum_squares", "branch_calls"):
            source = ROOT / (name + ".zzy")
            _, cls.outputs[name] = compile_file(source, Path(cls.workspace.name) / (name + ".exe"))

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def run_native(self, name, n, repeat=1):
        command = [str(self.outputs[name]), str(n)]
        if repeat != 1:
            command.append(str(repeat))
        return subprocess.run(command, text=True, capture_output=True, timeout=5, check=False)

    def test_squares_fixed_oracle_and_interpreter(self):
        with load_module(ROOT / "sum_squares.zzy") as module:
            for n in (-3, 0, 1, 5, 1000, 10000):
                expected = 0 if n < 0 else n * (n - 1) * (2 * n - 1) // 6
                self.assertEqual(module.call("bench", n).value, expected)
                result = self.run_native("sum_squares", n)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, f"{expected}\n")

    def test_calls_branch_and_floor_modulo(self):
        with load_module(ROOT / "branch_calls.zzy") as module:
            self.assertEqual(module.call("term", -1).value, -2)
            for n in (-3, 0, 1, 2, 5, 1000):
                count = max(n, 0)
                expected = count * (count - 1) // 2 + count % 2
                self.assertEqual(module.call("bench", n).value, expected)
                result = self.run_native("branch_calls", n)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, f"{expected}\n")

    def test_batch_prevents_disappearing_work(self):
        n, repeat = 10000, 100
        expected = n * (n - 1) * (2 * n - 1) // 6
        result = self.run_native("sum_squares", n, repeat)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f"{expected} {expected * repeat}\n")

    def test_overflow_is_explicit_subset_failure(self):
        result = self.run_native("sum_squares", 3_100_000)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Int64 overflow", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertGreater(3_100_000 * 3_099_999 * 6_199_999 // 6, (1 << 63) - 1)

    def test_negative_modulo_uses_zzy_floor_rule(self):
        with TemporaryDirectory() as temporary:
            sample = Path(temporary) / "modulo.zzy"
            sample.write_text('(addnew) bench(n: (Int)) -> (Int) {\n'
                              '    (return) n % 2;\n}\n', encoding="utf-8")
            with load_module(sample) as module:
                _, binary = compile_file(sample, Path(temporary) / "modulo.exe")
                for n in (-3, -2, -1, 0, 1, 2, 3):
                    expected = n % 2
                    self.assertEqual(module.call("bench", n).value, expected)
                    result = subprocess.run([str(binary), str(n)], capture_output=True,
                                            text=True, timeout=5, check=False)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, f"{expected}\n")

    def test_unsupported_code_rejected_without_execution(self):
        with TemporaryDirectory() as temporary:
            sample = Path(temporary) / "side_effect.zzy"
            sample.write_text((ROOT / "sum_squares.zzy").read_text(encoding="utf-8")
                              + '\nio.print("MUST_NOT_RUN");\n', encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output), self.assertRaisesRegex(Unsupported, "top level"):
                render_file(sample)
            self.assertEqual(output.getvalue(), "")

    def test_unsupported_array_and_recursive_call(self):
        with TemporaryDirectory() as temporary:
            sample = Path(temporary) / "unsupported.zzy"
            sample.write_text('(addnew) bench(n: (Int)) -> (Int) {\n'
                              '    (zno) values := [n];\n'
                              '    (return) n;\n}\n', encoding="utf-8")
            with self.assertRaisesRegex(Unsupported, "array"):
                render_file(sample)
            sample.write_text('(addnew) bench(n: (Int)) -> (Int) {\n'
                              '    (return) bench(n);\n}\n', encoding="utf-8")
            with self.assertRaisesRegex(Unsupported, "recursive"):
                render_file(sample)

    def test_output_deterministic(self):
        source = ROOT / "sum_squares.zzy"
        self.assertEqual(render_file(source), render_file(source))


if __name__ == "__main__":
    unittest.main()
