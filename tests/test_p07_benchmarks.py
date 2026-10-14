"""Real paired CLI results and measurement guardrails; not speed assertions."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from benchmarks.common import BASE, ROOT, expected, load_manifest, source, validate
from benchmarks.reference import CheckedArray, Machine, query, quantity_add
from benchmarks.run import collect, summarize
from benchmarks.worker import sample
from fractions import Fraction
from zzy.diagnostics import ResourceExceeded
from zzy.process import run_bounded
from zzy.resources import ResourcePolicy


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ZZY P07 ')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.cases = load_manifest()['cases']

    def test_fixed_answers_and_real_paired_cli(self):
        answers=json.loads((BASE/'expected-small.json').read_text())['results']
        self.assertEqual(len(answers),9)
        for case in self.cases:
            self.assertEqual(expected(case['id'],10),answers[case['id']])
            for language in ('zzy','python'):
                with self.subTest(case=case['id'],language=language):
                    path=self.directory/(case['id']+('.zzy' if language=='zzy' else '.py'))
                    path.write_bytes(source(case,language,10))
                    row=collect(language,'cli_total',case['id'],10,path)
                    self.assertEqual(row['status'],'ok',row)
                    if language=='zzy':
                        result=run_bounded([sys.executable,'-X','utf8','-m','zzy','check',str(path)],
                            cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT)),timeout=10)
                        self.assertEqual(result,(0,b'',b''))

    def test_batch_state_isolation_boundaries_and_cleanup(self):
        for case in self.cases:
            for language in ('zzy','python'):
                for n in ([1,2] if case['id']=='B06' else [0,1,2]):
                    with self.subTest(case=case['id'],language=language,n=n):
                        path=self.directory/(case['id']+('.zzy' if language=='zzy' else '.py'))
                        path.write_bytes(source(case,language,n))
                        result=sample(path,language,case['id'],n,batch=2)
                        self.assertTrue(result['result_check'])
                        self.assertEqual(result['batch'],2)
                        self.assertGreater(result['timings']['execute_ns'],0)

    def test_manifest_cannot_silently_collect_zero_or_drop_contract(self):
        original=load_manifest()
        for changed in ({'schema_version':1,'cases':[]},
                        dict(original,cases=original['cases'][:-1]),
                        dict(original,cases=[original['cases'][0]]*9)):
            path=self.directory/'bad.json'
            path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):load_manifest(path)
        for field in ('samples','sizes','resource_fingerprint','zzy_file'):
            changed=json.loads(json.dumps(original))
            changed['cases'][0][field]={'samples':0,'sizes':[10],'resource_fingerprint':'bad','zzy_file':'missing.zzy'}[field]
            path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):load_manifest(path)

    def test_reference_validation_partial_sums_and_failed_transition(self):
        for values in ([True],[1,False],[1,'x']):
            checked=CheckedArray(values)
            self.addCleanup(checked.close)
            with self.assertRaises(TypeError):checked.sum()
            with self.assertRaises(TypeError):checked.sorted()
        checked=CheckedArray([8,8],ResourcePolicy({'integer_bits':4}))
        self.addCleanup(checked.close)
        with self.assertRaises(ResourceExceeded):checked.sum()
        self.assertEqual(checked.values,[8,8])
        self.assertEqual(query([]),[])
        with self.assertRaises(TypeError):query([{'id':0,'done':False,'priority':True}],take=0)
        with self.assertRaises(TypeError):query([{'id':0,'done':1,'priority':0}])
        graph={('a','flip'):'b',('b','flip'):'a'}
        machine=Machine(graph,'a')
        self.assertFalse(machine.send('missing')[0])
        self.assertEqual(machine.state,'a')
        self.assertEqual(machine.send('flip'),(True,'b'))
        self.assertEqual(Machine(graph,'a').state,'a')
        with self.assertRaises(ValueError):quantity_add((Fraction(1),(0,1)),(Fraction(1),(1,0)))

    def test_wrong_answer_sort_mutation_timeout_and_error_are_failures(self):
        with self.assertRaises(AssertionError):validate('B01',10,44)
        with self.assertRaises(AssertionError):validate('B05',10,list(range(10)),list(range(10)))
        path=self.directory/'bad.py'
        path.write_text('print(999)')
        self.assertEqual(collect('python','cli_total','B01',10,path)['status'],'wrong_result')
        path.write_text('while True: pass')
        timeout=collect('python','cli_total','B01',10,path,timeout=0.2)
        self.assertEqual(timeout['status'],'timeout')
        with patch('benchmarks.run.run_bounded',side_effect=AssertionError('overflow')):
            error=collect('python','cli_total','B01',10,path)
        self.assertEqual(error['status'],'error')
        report=summarize([dict(timeout,phase='sample'),dict(error,phase='sample')])
        self.assertEqual(report['statistics'],[])
        self.assertEqual(len(report['failures']),2)

    def test_summary_excludes_warmup_reports_mad_and_counts(self):
        rows=[dict(case='B01',n=10,language='zzy',scope='cli_total',status='ok',phase='sample',elapsed_ns=x) for x in (1,2,9)]
        rows.append(dict(rows[0],phase='warmup',elapsed_ns=999))
        result=summarize(rows)['statistics'][0]
        self.assertEqual((result['samples'],result['median_ns'],result['mad_ns']),(3,2,1))


if __name__=='__main__':unittest.main()
