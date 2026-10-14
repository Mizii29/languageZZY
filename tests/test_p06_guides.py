"""Executable documentation, fixed spec output and aggregate-runner guards."""
import io
import json
import os
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

from tests.blackbox import ROOT
from tests.__main__ import execute
from zzy.process import run_bounded


class GuideTests(unittest.TestCase):
    def test_every_guide_block_is_mapped_and_matches_executable_source(self):
        entries=json.loads((ROOT/'tests/p06/guide/manifest.json').read_text(encoding='utf-8'))
        self.assertTrue(entries)
        seen=set()
        for doc in ('skills/syntax.md','skills/guide.md'):
            blocks=re.findall(r'```zzy\n(.*?)\n```',(ROOT/doc).read_text(encoding='utf-8'),re.S)
            self.assertTrue(blocks)
            for index,block in enumerate(blocks,1):
                matches=[entry for entry in entries if entry['document']==doc and entry['block']==index]
                self.assertEqual(len(matches),1,(doc,index))
                self.assertEqual((ROOT/matches[0]['file']).read_text(encoding='utf-8'),block+'\n')
                seen.add((doc,index))
        self.assertEqual(len(seen),len(entries))
        self.assertEqual((ROOT/'tests/p06/guide/syntax-12/helpers.zzy').read_bytes(),(ROOT/'tests/p06/guide/syntax-11/helpers.zzy').read_bytes())

    def spec(self,file,count,expected,trace=False):
        status,out,err=run_bounded([sys.executable,'-X','utf8','-m','zzy','test',file,'--diagnostic-format','json'],
            cwd=ROOT,env=dict(os.environ),timeout=30)
        self.assertEqual(status,0,err)
        lines=out.decode().splitlines(keepends=True)
        self.assertEqual(''.join(lines[:-1]),expected)
        self.assertEqual(json.loads(lines[-1]),dict(schema_version=1,tests=count,passed=count,failed=0,timed_out=0,collection_errors=0))
        if trace:
            records=[json.loads(line) for line in err.splitlines()]
            self.assertEqual(len(records),1)
            self.assertEqual((records[0]['kind'],records[0]['code'],records[0]['message']),('trace',None,'1'))
            self.assertEqual(records[0]['span'],dict(start=dict(line=4,column=11),end=dict(line=4,column=20)))
        else:self.assertEqual(err,b'')

    def test_metamorphic_specs_with_fixed_external_answers(self):
        self.spec('tests/p06/specs',9,''.join(name+':ok\n' for name in ('sum','stats','with','json','unit','machine','query','pipe','sort')))

    def test_guide_spec_and_file_functions(self):
        self.spec('tests/p06/guide/syntax-13/main.zzy',1,'',trace=True)
        self.spec('tests/p06/guide/guide-1/main.zzy',1,'15\n')
        self.spec('tests/p06/guide/guide-2/spec.zzy',3,'save:ok\nvalidation:ok\nfailures:ok\n')

    def test_one_command_rejects_empty_incomplete_skipped_and_expected_failure(self):
        self.assertFalse(execute(unittest.TestSuite(),io.StringIO())[0])
        for number,skipped,expected in ((0,[],[]),(1,[('x','skip')],[]),(1,[],[('x','expected')])):
            result=unittest.TestResult();result.testsRun=number;result.skipped=skipped;result.expectedFailures=expected
            with patch('tests.__main__.unittest.TextTestRunner.run',return_value=result):
                self.assertFalse(execute(unittest.TestSuite([unittest.FunctionTestCase(lambda:None)]),io.StringIO())[0])

    def test_coverage_matrix_references_every_core_rule_and_real_cases(self):
        from tests.blackbox import DEFAULT_MANIFESTS, load_cases
        matrix=json.loads((ROOT/'tests/p06/coverage.json').read_text())
        plan=(ROOT/'docs/development/test-coverage.md').read_text(encoding='utf-8').split('## 2.')[0]
        rules=set(re.findall(r'^\| ([A-Z]+-\d+) \|',plan,re.M))
        self.assertEqual(set(matrix),rules)
        cases={c['mode']+':'+c['id']:c for manifest in DEFAULT_MANIFESTS for c in load_cases(manifest)}
        for rule,examples in matrix.items():
            self.assertEqual(set(examples),{'normal','boundary','error'})
            for role,identity in examples.items():
                self.assertIn(identity,cases,(rule,role))
                if role=='normal':self.assertEqual(cases[identity]['exit_code'],0,identity)
                if role=='error':self.assertNotEqual(cases[identity]['exit_code'],0,identity)
