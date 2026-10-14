"""Independent stdin/files/outputs for the guide-only Agent exercise."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from tests.blackbox import ROOT
from zzy.process import run_bounded


class AgentPracticeTests(unittest.TestCase):
    def cli(self,root,mode='run',stdin=b'minutes.json\n',file='main.zzy'):
        return run_bounded([sys.executable,'-X','utf8','-m','zzy',mode,str(ROOT/'examples/agent-practice'/file),'--diagnostic-format','json'],cwd=root,env=dict(os.environ,PYTHONPATH=str(ROOT)),stdin=stdin,timeout=15)

    def test_normal_empty_and_recoverable_validation_preserve_old_file(self):
        for data,expected,report in (
            ('[30,15,0]','共 3 项，45 分钟\n',b'{"count":3,"minutes":45}'),
            ('[]','共 0 项，0 分钟\n',b'{"count":0,"minutes":0}'),
            ('[true]','分钟必须为非负整数\n',b'old'),
            ('[-1]','分钟必须为非负整数\n',b'old'),
            ('[1.0]','分钟必须为非负整数\n',b'old'),
            ('[null]','分钟必须为非负整数\n',b'old'),
            ('{}','数据必须为分钟数组\n',b'old')):
            with self.subTest(data=data),tempfile.TemporaryDirectory(prefix='ZZY practice 中文 ') as directory:
                root=Path(directory);(root/'minutes.json').write_text(data);(root/'report.json').write_bytes(b'old')
                self.assertEqual(self.cli(root), (0,expected.encode(),b''))
                self.assertEqual((root/'report.json').read_bytes(),report)
                self.assertFalse(list(root.glob('.zzy-*.tmp')))

    def test_parse_read_save_failure_eof_and_check(self):
        with tempfile.TemporaryDirectory(prefix='ZZY practice ') as directory:
            root=Path(directory);report=root/'report.json';report.write_bytes(b'old')
            for payload in (None,'[','[NaN]'):
                if payload is not None:(root/'minutes.json').write_text(payload)
                status,out,err=self.cli(root)
                self.assertEqual((status,err),(0,b''));self.assertTrue(out);self.assertNotIn('共 '.encode(),out)
                self.assertEqual(report.read_bytes(),b'old')
            self.assertEqual(self.cli(root,stdin=b''),(0,'取消\n'.encode(),b''));self.assertEqual(report.read_bytes(),b'old')
            self.assertEqual(self.cli(root,mode='check'),(0,b'',b''));self.assertEqual(report.read_bytes(),b'old')
            report.unlink();report.mkdir();(root/'minutes.json').write_text('[1]')
            self.assertEqual(self.cli(root),(0,'保存失败\n'.encode(),b''))
            self.assertTrue(report.is_dir());self.assertFalse(list(root.glob('.zzy-*.tmp')))

    def test_specs(self):
        with tempfile.TemporaryDirectory() as directory:
            status,out,err=self.cli(directory,mode='test',file='spec.zzy')
            self.assertEqual((status,err),(0,b''))
            self.assertEqual(json.loads(out),dict(schema_version=1,tests=2,passed=2,failed=0,timed_out=0,collection_errors=0))
