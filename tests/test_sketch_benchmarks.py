"""Benchmark success must require collected work and an actual GUI."""
import subprocess
import sys
import unittest
from unittest.mock import patch


class SketchBenchmarkTests(unittest.TestCase):
    def test_zero_repeats_rejected(self):
        for module,extra in [('run',[]),('render',['--all']),('seek',['--all'])]:
            result=subprocess.run([sys.executable,'-X','utf8','-m','benchmarks.sketch.'+module,*extra,'--repeats','0'],capture_output=True,timeout=10)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertIn(b'repeats must be positive',result.stderr)

    def test_gui_fallback_cannot_count_as_render_success(self):
        from benchmarks.sketch import render
        from zzy.interpreter import Interpreter
        def headless(program,output,**kwargs):Interpreter(program,output).run()
        with patch.object(render,'run_gui',headless):
            with self.assertRaisesRegex(RuntimeError,'real GUI benchmark'):
                render.sample(1,'single')


if __name__=='__main__':unittest.main()
