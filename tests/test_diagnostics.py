import io
import json
import unittest

from zzy.diagnostics import Diagnostic, Phase, Position, ResourceExceeded, Span, render
from zzy.output import Output
from zzy.resources import ResourceMeter, ResourcePolicy


class DiagnosticTests(unittest.TestCase):
    def test_text_and_json_share_coordinates(self):
        diagnostic = Diagnostic("名称 total 尚未声明", "E302", "name.zzy",
                                Span(Position(1, 10), Position(1, 15)), ("请先声明。",))
        self.assertTrue(render(diagnostic).startswith("name.zzy:1:10: E302 "))
        record = json.loads(render(diagnostic, "json"))
        self.assertEqual(record, {"schema_version": 1, "kind": "error", "code": "E302",
                                 "file": "name.zzy", "span": {"start": {"line": 1, "column": 10},
                                 "end": {"line": 1, "column": 15}}, "message": diagnostic.message,
                                 "notes": ["请先声明。"]})

    def test_non_error_kinds_have_no_code(self):
        for kind in ("cancelled", "trace", "internal_error"):
            diagnostic = Diagnostic("消息", kind=kind)
            self.assertIsNone(json.loads(render(diagnostic, "json"))["code"])
            self.assertNotIn("E201", render(diagnostic))
        with self.assertRaises(ValueError):
            Diagnostic("bad", "E201", kind="trace")

    def test_final_record_fits_unicode_and_escaped_json(self):
        diagnostic = Diagnostic('😀\n"' * 10000, "E211", "很长的路径" * 10000,
                                notes=("note" * 10000,) * 100)
        for format in ("text", "json"):
            text = render(diagnostic, format)
            self.assertLessEqual(len(text.encode("utf-8")), 4096)
            self.assertTrue(text.endswith("\n"))
            if format == "json":
                self.assertEqual(len(text.splitlines()), 1)
                self.assertIsNone(json.loads(text)["file"])
                self.assertEqual(json.loads(text)["code"], "E211")

    def test_output_budget_checks_utf8_before_write(self):
        out, err = io.StringIO(), io.StringIO()
        output = Output(out, err, ResourceMeter(ResourcePolicy({"stdout_bytes": 4}), Phase.EXECUTION))
        output.write("中")
        output.write("\n")
        with self.assertRaises(ResourceExceeded) as caught:
            output.write("x")
        self.assertEqual(out.getvalue(), "中\n")
        self.assertEqual(caught.exception.exit_code, 1)
        self.assertEqual(output.meter.used("stdout_bytes"), 4)

    def test_default_output_boundary_and_emergency_once(self):
        out, err = io.StringIO(), io.StringIO()
        output = Output(out, err, ResourceMeter(ResourcePolicy(), Phase.EXECUTION), "json")
        output.write("a" * (1024**2 - 1))
        output.write("b")
        with self.assertRaises(ResourceExceeded) as caught:
            output.write("c")
        output.final(caught.exception.diagnostic)
        output.final(caught.exception.diagnostic)
        self.assertEqual(len(out.getvalue()), 1024**2)
        self.assertEqual(len(err.getvalue().splitlines()), 1)
        self.assertEqual(json.loads(err.getvalue())["code"], "E211")

    def test_stderr_exhaustion_uses_reserve(self):
        out, err = io.StringIO(), io.StringIO()
        output = Output(out, err, ResourceMeter(ResourcePolicy({"stderr_bytes": 1}), Phase.FRONTEND), "json")
        output.failure(Diagnostic("cannot read", "E401"))
        self.assertEqual(out.getvalue(), "")
        self.assertLessEqual(len(err.getvalue().encode("utf-8")), 4096)
        self.assertEqual(json.loads(err.getvalue())["code"], "E211")
        self.assertIn("stderr_bytes", json.loads(err.getvalue())["message"])
