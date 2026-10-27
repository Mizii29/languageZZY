"""Diagnostic paths remain correct across changing cwd and execution contexts."""
import io
import os
from pathlib import Path
import tempfile
import unittest

from zzy.diagnostics import DiagnosticError, Phase, display_path
from zzy.interpreter import Interpreter
from zzy.output import Output
from zzy.prepare import prepare
from zzy.resources import ResourceMeter, ResourcePolicy
from zzy.source import Source


class DiagnosticLocationTests(unittest.TestCase):
    def setUp(self):
        self.original=Path.cwd()
        temp=tempfile.TemporaryDirectory(prefix='ZZY P07 路径 ')
        self.addCleanup(temp.cleanup)
        self.addCleanup(os.chdir,self.original)
        self.first=Path(temp.name)/'first'
        self.second=Path(temp.name)/'second'
        self.first.mkdir()
        self.second.mkdir()
        self.path=self.first/'source.zzy'

    def program(self,text):
        return prepare(Source.from_bytes(self.path,text.encode()),
                       ResourceMeter(ResourcePolicy(),Phase.FRONTEND))

    def runtime(self,program,stdin=None):
        output=Output(io.StringIO(),io.StringIO(),ResourceMeter(ResourcePolicy(),Phase.EXECUTION))
        return Interpreter(program,output,stdin)

    def assert_error(self,runtime):
        with self.assertRaises(DiagnosticError) as caught:
            runtime.run()
        diagnostic=caught.exception.diagnostic
        self.assertEqual(diagnostic.code,'E205')
        self.assertEqual(diagnostic.file,display_path(self.path))
        self.assertEqual(diagnostic.span.start.line,2)
        for key in ('runtime_objects','runtime_slots','runtime_payload_bytes'):
            self.assertEqual(runtime.meter.used(key),0)
        self.assertIsNone(runtime.frame)
        self.assertFalse(runtime.bindings)
        return diagnostic

    def test_directory_change_inside_input_keeps_later_error_location(self):
        program=self.program('io.input("");\nio.print(1 / 0);')
        destination=self.second
        class MovingInput:
            def read(self,count):
                os.chdir(destination)
                return '\n'
        os.chdir(self.first)
        error=self.assert_error(self.runtime(program,MovingInput()))
        self.assertEqual(error.file,'../first/source.zzy')
        self.assertEqual(error.span.start.column,12)

    def test_reused_program_and_runtime_do_not_share_stale_paths(self):
        program=self.program('(zno) value := 1;\nio.print(value / 0);')
        runtime=self.runtime(program)
        for directory in (self.first,self.second,self.first):
            os.chdir(directory)
            self.assert_error(runtime)
            self.assert_error(self.runtime(program))

        if os.name == 'nt':
            import ctypes
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.GetShortPathNameW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint]
            kernel.GetShortPathNameW.restype=ctypes.c_uint
            buffer=ctypes.create_unicode_buffer(32768)
            self.assertTrue(kernel.GetShortPathNameW(str(self.first),buffer,len(buffer)))
            os.chdir(buffer.value)
            self.assertEqual(display_path(self.path),'source.zzy')
            self.assertEqual(display_path(Path('missing.zzy')),'missing.zzy')
            self.assert_error(self.runtime(program))


if __name__=='__main__':unittest.main()
