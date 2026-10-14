import io
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from zzy.diagnostics import Cancelled, DiagnosticError, Phase, ResourceExceeded
from zzy.interpreter import Interpreter
from zzy.output import Output
from zzy.prepare import prepare
from zzy.resources import ResourceMeter, ResourcePolicy
from zzy.source import Source


def prepared(text, limits=None):
    meter = ResourceMeter(ResourcePolicy(limits or {}), Phase.FRONTEND)
    program = prepare(Source.from_bytes(Path("test.zzy"), text.encode("utf-8")), meter)
    output = Output(io.StringIO(), io.StringIO(), meter)
    return program, output


class InterpreterTests(unittest.TestCase):
    def assert_released(self, meter):
        for key in ("runtime_objects", "runtime_slots", "runtime_payload_bytes"):
            self.assertEqual(meter.used(key), 0, key)

    def test_program_reuse_has_fresh_bindings_and_no_preparation_output(self):
        program, output = prepared('(zyes) x := 2; x <- x + 3; io.print(x);')
        self.assertEqual(output.stdout.getvalue(), "")
        for _ in range(2):
            Interpreter(program, output).run()
            self.assert_released(output.meter)
        self.assertEqual(output.stdout.getvalue(), "5\n5\n")
        with self.assertRaises(TypeError):
            program.integers[0] = 10

    def test_error_and_cancel_release_even_with_live_traceback(self):
        for text, failure in (
            ('(zno) x := "held"; x + 1;', DiagnosticError),
            ('(zno) x := "held"; io.print(x);', Cancelled),
            ('(zno) x := "held"; io.print(x);', MemoryError),
        ):
            program, output = prepared(text)
            interpreter = Interpreter(program, output)
            try:
                if failure is DiagnosticError:
                    interpreter.run()
                else:
                    with patch.object(output, "write", side_effect=failure):
                        interpreter.run()
            except failure as error:
                self.assertIsNotNone(error.__traceback__)
                self.assert_released(output.meter)
                self.assertEqual(interpreter.bindings, {})
            else:
                self.fail("expected execution failure")

    def test_resource_failure_releases_existing_values(self):
        program, output = prepared('(zno) x := "ab"; "c";', {"runtime_payload_bytes": 8})
        try:
            Interpreter(program, output).run()
        except ResourceExceeded as error:
            self.assertEqual(error.phase, Phase.EXECUTION)
            self.assert_released(output.meter)
        else:
            self.fail("expected resource failure")

    def test_exact_addition_width_across_byte_carries(self):
        program, output = prepared('1;')
        interpreter = Interpreter(program, output)
        pairs = [(0, 0), (127, 128), (255, 1), (256, 256), (65535, 1)]
        rng = random.Random(29)
        for bits in (1, 8, 9, 63, 64, 255, 4096, 65536):
            pairs.extend((rng.getrandbits(bits), rng.getrandbits(bits)) for _ in range(8))
        for left, right in pairs:
            self.assertEqual(interpreter.add_bits(left, right), (left + right).bit_length())

    def test_cancellation_inside_sum_scratch(self):
        program, output = prepared('1;')
        output.meter.cancellation.cancel()
        with self.assertRaises(Cancelled):
            Interpreter(program, output).add_bits(255, 1)

    def test_ast_spans_and_left_association(self):
        program, _ = prepared('io.print(1 + 2 + 3);')
        call = program.root.children[0].children[0]
        addition = call.children[1]
        self.assertEqual(addition.kind, "add")
        self.assertEqual(addition.children[0].kind, "add")
        self.assertEqual((call.start, call.end), (0, 19))
        self.assertEqual((addition.start, addition.end), (9, 18))
