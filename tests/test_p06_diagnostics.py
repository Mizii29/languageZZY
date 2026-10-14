"""Text/JSON parity, original-source EOF coordinates and CLI fault separation."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from tests.blackbox import ROOT, load_cases
from zzy.cli import main
from zzy.process import run_bounded


class DiagnosticCliTests(unittest.TestCase):
    def test_four_contract_examples_text_and_json_agree(self):
        cases=[c for c in load_cases(ROOT/'tests/p06/cases.json') if c['mode']=='run' and c['id'].startswith('p06-diagnostic-')]
        self.assertEqual(len(cases),4)
        for case in cases:
            with self.subTest(case=case['id']):
                results=[]
                for format in ('text','json'):
                    result=run_bounded([sys.executable,'-X','utf8','-m','zzy','run',case['file'],'--diagnostic-format',format],cwd=ROOT,env=dict(os.environ))
                    self.assertEqual((result[0],result[1]),(case['exit_code'],b''));results.append(result[2])
                record=json.loads(results[1]);start=case['diagnostic']['span'][:2]
                prefix=f"{case['file']}:{start[0]}:{start[1]}: {case['diagnostic']['code']} "
                self.assertTrue(results[0].decode().startswith(prefix))
                self.assertIn(record['message'],results[0].decode())

    def test_bom_crlf_unicode_tab_and_eof_zero_width(self):
        with tempfile.TemporaryDirectory(prefix='ZZY 中文 空格 ') as directory:
            root=Path(directory);file=root/'中文 空格.zzy'
            file.write_bytes(b'\xef\xbb\xbf'+'io.print("😀");\r\n\tio.print('.encode())
            for mode in ('run','check'):
                status,out,err=run_bounded([sys.executable,'-m','zzy',mode,file.name,'--diagnostic-format','json'],cwd=root,env=dict(os.environ,PYTHONPATH=str(ROOT)))
                self.assertEqual((status,out),(2,b''));record=json.loads(err)
                self.assertEqual(record['code'],'E103');self.assertEqual(record['file'],file.name)
                self.assertEqual(record['span'],dict(start=dict(line=2,column=11),end=dict(line=2,column=11)))

    def test_internal_runtime_fault_is_not_user_type_error(self):
        out,err=io.StringIO(),io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err),patch('zzy.interpreter.Interpreter.statement',side_effect=RuntimeError('test defect')):
            status=main(['run',str(ROOT/'examples/hello.zzy'),'--diagnostic-format','json'])
        self.assertEqual((status,out.getvalue()),(1,''))
        record=json.loads(err.getvalue());self.assertEqual((record['kind'],record['code']),('internal_error',None))
        self.assertNotIn('Traceback',err.getvalue())
