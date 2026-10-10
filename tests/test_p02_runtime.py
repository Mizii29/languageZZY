import gc
import io
import random
import unittest
from unittest.mock import patch

from tests.test_interpreter import prepared
from zzy.diagnostics import Cancelled, DiagnosticError, ResourceExceeded
from zzy.interpreter import Interpreter
from zzy.values import Array, Value


class P02RuntimeTests(unittest.TestCase):
    def released(self, meter):
        for key in ("runtime_objects", "runtime_slots", "runtime_payload_bytes"):
            self.assertEqual(meter.used(key), 0, key)

    def test_reused_program_has_fresh_arrays_shapes_and_input(self):
        program, output = prepared('(shape) S {x := [];} (zno) s := S::{}; '
                                   'array.push(s.x, io.input("")); io.print(s.x);')
        for text in ("a\n", "b\n"):
            Interpreter(program, output, io.StringIO(text)).run()
            self.released(output.meter)
        self.assertEqual(output.stdout.getvalue(), "[a]\n[b]\n")

    def test_array_versions_and_rejected_mutation_are_atomic(self):
        program, output = prepared('1;')
        runtime = Interpreter(program, output)
        node = program.root
        a = Array(runtime, node)
        a.push(Value("Int", 1), runtime, node)
        self.assertEqual((a.structural_version, a.content_version), (1, 1))
        a.replace(0, Value("Int", 2), runtime, node)
        self.assertEqual((a.structural_version, a.content_version), (1, 2))
        a.active = 2
        before = (a.data[:], output.meter.used("runtime_slots"))
        for operation in (lambda: a.push(Value("Int", 3), runtime, node),
                          lambda: a.pop(runtime, node)):
            with self.assertRaises(DiagnosticError) as caught:
                operation()
            self.assertEqual(caught.exception.diagnostic.code, "E206")
            self.assertEqual((a.data, output.meter.used("runtime_slots")), before)
            self.assertEqual((a.structural_version, a.content_version), (1, 2))
        a.active = 0
        self.assertEqual(a.pop(runtime, node).data, 2)
        self.assertEqual((a.structural_version, a.content_version), (2, 3))
        del a
        self.released(output.meter)

    def test_nested_iteration_failure_and_cancellation_release_counts(self):
        for failure in (DiagnosticError, Cancelled, MemoryError):
            text = '(zno) a := [1]; (for) x (in) a {(for) y (in) a {io.print(x);}}'
            program, output = prepared(text)
            runtime = Interpreter(program, output)
            arrays = []
            original = Array.__init__
            def remember(value, *args):
                original(value, *args)
                arrays.append(value)
            def fail(*args):
                self.assertEqual(arrays[0].active, 2)
                if failure is DiagnosticError:
                    runtime.error(program.root, "E205", "injected")
                raise failure()
            with patch.object(Array, "__init__", remember), patch.object(output, "write", fail):
                with self.assertRaises(failure):
                    runtime.run()
            self.assertEqual(arrays[0].active, 0)
            self.released(output.meter)

    def test_array_quota_failure_preserves_contents_versions_and_slots(self):
        program, output = prepared('1;', {"container_items": 1})
        runtime = Interpreter(program, output)
        a = Array(runtime, program.root)
        a.push(Value("Int", 1), runtime, program.root)
        with self.assertRaises(ResourceExceeded):
            a.push(Value("Int", 2), runtime, program.root)
        self.assertEqual([v.data for v in a.data], [1])
        self.assertEqual((a.structural_version, a.content_version), (1, 1))
        self.assertEqual(output.meter.used("runtime_slots"), 1)
        del a
        self.released(output.meter)

    def test_input_prompt_is_flushed_before_read_and_errors_are_not_eof(self):
        for kind in (OSError, UnicodeError):
            program, output = prepared('io.input("prompt");')
            stream = io.StringIO()
            def read(count):
                self.assertEqual(output.stdout.getvalue(), "prompt")
                raise kind("injected")
            with patch.object(stream, "read", read):
                with self.assertRaises(DiagnosticError) as caught:
                    Interpreter(program, output, stream).run()
            self.assertEqual(caught.exception.diagnostic.code, "E401")
            self.released(output.meter)

    def test_lexical_type_identity_survives_inner_shadow(self):
        program, output = prepared('(shape) S {} { (zno) Alias := S; (zno) S := 1; '
                                   '(zno) x: Alias := Alias::{}; io.print(x); }')
        Interpreter(program, output).run()
        self.assertEqual(output.stdout.getvalue(), "S::{}\n")
        self.released(output.meter)

    def test_signed_arithmetic_against_independent_host_operations(self):
        program, output = prepared('0;')
        runtime = Interpreter(program, output)
        rng = random.Random(402)
        for _ in range(200):
            a, b = rng.randrange(-100000, 100000), rng.randrange(-100000, 100000) or 1
            for name, expected in (("PLUS", a+b), ("MINUS", a-b), ("MULTIPLY", a*b),
                                   ("FLOOR_DIVIDE", a//b), ("REMAINDER", a%b)):
                value = runtime.integer_operation(name, a, b, program.root)
                self.assertEqual(value.data, expected)
                del value
                self.released(output.meter)

    def test_cycles_reclaim_before_live_budget_rejects(self):
        program, output = prepared('1;', {"runtime_objects": 1})
        runtime = Interpreter(program, output)
        for _ in range(10):
            a = Array(runtime, program.root)
            a.push(a, runtime, program.root)
            del a
        gc.collect()
        self.released(output.meter)

    def test_streamed_integer_widths_match_exact_results(self):
        program, output = prepared('0;')
        runtime = Interpreter(program, output)
        rng = random.Random(219)
        for bits in (0, 1, 7, 8, 9, 16, 64, 128, 511):
            for _ in range(12):
                a, b = rng.getrandbits(bits), rng.getrandbits(bits)
                self.assertEqual(runtime.product_bits(a, b), (a*b).bit_length())
                self.assertEqual(runtime.difference_bits(max(a,b), min(a,b)), abs(a-b).bit_length())

    def test_input_flush_and_per_read_budget(self):
        program, output = prepared('io.input("prompt");', {"io_payload_bytes": 2})
        stream = io.StringIO("x\n")
        events = []
        original_read = stream.read
        def read(count):
            self.assertEqual(events[0], "flush")
            return original_read(count)
        with patch.object(output.stdout, "flush", lambda: events.append("flush")), patch.object(stream, "read", read):
            Interpreter(program, output, stream).run()
        self.released(output.meter)
