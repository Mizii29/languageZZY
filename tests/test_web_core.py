"""Core-only adapter checks; optional HTTP dependencies are deliberately absent."""
import io
from pathlib import Path
import subprocess
import sys
import unittest
from zzy.web import RequestRuntime, BoundaryError
from zzy.prepare import prepare
from zzy.source import SourceLoader
from zzy.resources import ResourcePolicy, ResourceMeter
from zzy.diagnostics import Phase
from zzy.output import Output

ROOT = Path(__file__).resolve().parents[1]

class WebCoreTests(unittest.TestCase):
    def test_import_does_not_load_optional_dependencies(self):
        code = "import zzy.cli,zzy.web,sys; assert not any(x in sys.modules for x in ('starlette','uvicorn','tkinter'))"
        subprocess.run([sys.executable, '-c', code], cwd=ROOT, check=True)

    def test_independent_context_and_released_budget(self):
        policy = ResourcePolicy()
        meter = ResourceMeter(policy, Phase.FRONTEND)
        with SourceLoader(meter) as loader:
            program = prepare(loader.read(ROOT/'tests/p08/edge.zzy'), meter, loader)
        handler = next(n for n in program.root.children if n.token.lexeme == 'echo')
        for raw in ('true', '1', 'null', '"[OoO]n"'):
            output = Output(io.StringIO(), io.StringIO(), ResourceMeter(policy, Phase.EXECUTION))
            r = RequestRuntime(program, output, io.StringIO())
            r.handler, r.request_text, r.input_valid = handler, ('{}', raw), False
            r.run()
            self.assertEqual(r.result, (200, ('['+raw+',1]').encode()))
            self.assertFalse(r.bindings)
            for key in ('runtime_slots','runtime_objects','runtime_payload_bytes'):
                self.assertEqual(r.meter.used(key), 0)

    def test_example_check_is_silent(self):
        result = subprocess.run([sys.executable, '-m', 'zzy', 'check', 'examples/web/app.zzy'], cwd=ROOT, capture_output=True)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'',b''))
