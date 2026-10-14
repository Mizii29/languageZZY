"""Real CLI checks for the spec runner and trace's independent observable output."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.blackbox import ROOT
from tests.process import run_bounded
from zzy.diagnostics import Phase
from zzy.output import Output
from zzy.resources import ResourceMeter, ResourcePolicy
from zzy.spec_runner import run_specs


class P04SpecTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='ZZY spec tests 中文 ')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def source(self,name,text):
        file=self.root/name;file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(text,encoding='utf-8');return file

    def cli(self,mode,target,*extra,stdin=b''):
        return run_bounded([sys.executable,'-X','utf8','-m','zzy',mode,str(target),
                            '--diagnostic-format','json',*map(str,extra)],
                           cwd=self.root,env=dict(os.environ,PYTHONPATH=str(ROOT)),stdin=stdin,timeout=15)

    def summary(self,result,expected,stdout=''):
        status,out,err=result
        lines=out.decode('utf-8').splitlines(keepends=True)
        self.assertTrue(lines,'runner must report a nonempty summary')
        summary=json.loads(lines[-1])
        self.assertEqual(summary,dict(schema_version=1,**expected))
        self.assertEqual(''.join(lines[:-1]),stdout)
        self.assertNotIn(b'Traceback',err)
        self.assertEqual(status,0 if expected['passed']==expected['tests'] and expected['tests']>0 and not expected['collection_errors'] else 1)
        return [json.loads(line) for line in err.decode('utf-8').splitlines()]

    def test_each_spec_reinitializes_cells_arrays_machine_lazy_and_input(self):
        file=self.source('isolation.zzy','(machine) M {a -- "go" --> b;}(zno)p:=M("a");'
            '(zyes)n:=0;(zno)a:=[];(addnew) next(){n<-n+1;(return)n;}(zno)v:=(zzz)(next());'
            '(spec) "first" {(o_o)len(a)==0;(o_o)n==0;(o_o)p.state=="a";array.push(a,1);'
            '(o_o)wake(v)==1;(o_o)(p<<"go")==(^_^)("b");io.print(io.input(""));}'
            '(spec) "second" {(o_o)len(a)==0;(o_o)n==0;(o_o)p.state=="a";(o_o)wake(v)==1;io.print(io.input(""));}')
        records=self.summary(self.cli('test',file,stdin=b'not inherited\n'),dict(tests=2,passed=2,failed=0,timed_out=0,collection_errors=0), 'null\nnull\n')
        self.assertEqual(records,[])

    def test_failed_spec_does_not_stop_next_spec(self):
        file=self.source('fail.zzy','(spec) "bad" {(o_o)(false);}\n(spec) "good" {io.print("continued");}')
        records=self.summary(self.cli('test',file),dict(tests=2,passed=1,failed=1,timed_out=0,collection_errors=0),'continued\n')
        self.assertEqual(records[0]['code'],'E210');self.assertEqual(records[0]['file'],'fail.zzy')
        self.assertEqual(records[0]['span']['start'],dict(line=1,column=15))

    def test_zero_specs_empty_directory_and_nonexistent_are_failures(self):
        file=self.source('none.zzy','io.print("must not initialize");')
        empty=self.root/'empty';empty.mkdir()
        for target in (file,empty,self.root/'missing.zzy'):
            with self.subTest(target=target):
                records=self.summary(self.cli('test',target),dict(tests=0,passed=0,failed=0,timed_out=0,collection_errors=1))
                self.assertEqual(records[0]['code'],'E401')

    def test_collection_error_prevents_initialization_of_valid_files(self):
        self.source('a.zzy','io.print("must not execute");(spec) "valid" {}')
        self.source('b.zzy','(spec) "bad" {unknown;}')
        records=self.summary(self.cli('test',self.root),dict(tests=1,passed=0,failed=0,timed_out=0,collection_errors=1))
        self.assertEqual(records[0]['code'],'E302')

    def test_directory_is_path_sorted_and_runs_only_selected_body(self):
        self.source('b.zzy','io.print("B");(spec) "b" {io.print("b");}')
        self.source('a.zzy','io.print("A");(spec) "a1" {io.print("1");}(spec) "a2" {io.print("2");}')
        records=self.summary(self.cli('test',self.root),dict(tests=3,passed=3,failed=0,timed_out=0,collection_errors=0),'A\n1\nA\n2\nB\nb\n')
        self.assertEqual(records,[])

    def test_timeout_is_failure_and_remaining_specs_run(self):
        file=self.source('timeout.zzy','(spec) "hang" {(while)(true){}}(spec) "next" {(o_o)(true);}')
        records=self.summary(self.cli('test',file,'--timeout','1.5'),dict(tests=2,passed=1,failed=0,timed_out=1,collection_errors=0))
        self.assertEqual(records[0]['code'],'E211');self.assertIn('hang',records[0]['message'])

    def test_output_over_limit_cannot_pass(self):
        file=self.source('output.zzy','(spec) "loud" {io.print("too much output");}')
        config=self.source('limits.json','{"policy_version":1,"limits":{"stdout_bytes":4}}')
        status,out,err=self.cli('test',file,'--limits',config)
        self.assertEqual(status,1);self.assertNotIn(b'Traceback',err)
        self.assertEqual(json.loads(err.splitlines()[-1])['code'],'E211')
        self.assertNotIn(b'"passed":1',out)

    def test_invalid_timeout_is_cli_failure(self):
        file=self.source('ok.zzy','(spec) "ok" {}')
        for timeout in ('0','-1','nan','inf'):
            status,out,err=self.cli('test',file,'--timeout',timeout)
            self.assertEqual(status,2);self.assertEqual(json.loads(err)['code'],'E401')

    def test_trace_evaluates_once_and_does_not_wake(self):
        file=self.source('trace.zzy','(zyes)n:=0;(addnew) f(){n<-n+1;(return)n;}\n'
            '(@_@) f();\n(@_@) (zzz)(f());\nio.print(n);')
        status,out,err=self.cli('run',file)
        self.assertEqual((status,out),(0,b'1\n'))
        records=[json.loads(line) for line in err.splitlines()]
        self.assertEqual([r['kind'] for r in records],['trace','trace'])
        self.assertEqual([r['message'] for r in records],['1','<lazy NEW>'])
        self.assertEqual(records[0]['span'],dict(start=dict(line=2,column=7),end=dict(line=2,column=10)))
        self.assertEqual(self.cli('check',file),(0,b'',b''))

    def test_worker_private_cwd_temp_and_immutable_collected_bytes(self):
        file=self.source('snapshot.zzy','(spec) "one" {io.print("original");}(spec) "two" {io.print("original");}')
        policy=ResourcePolicy();output=Output(io.StringIO(),io.StringIO(),ResourceMeter(policy,Phase.FRONTEND),'json')
        actual=run_bounded;directories=[]
        def inspect(command,**kwargs):
            directory=Path(kwargs['cwd']);directories.append(directory)
            self.assertEqual(kwargs['env']['TMP'],str(directory));self.assertEqual(kwargs['env']['TEMP'],str(directory))
            self.assertNotEqual(directory,self.root)
            if len(directories)==1:file.write_text('broken replacement',encoding='utf-8')
            return actual(command,**kwargs)
        with patch('zzy.spec_runner.run_bounded',inspect):status=run_specs(file,output,policy,10)
        self.assertEqual(status,0);self.assertTrue(output.stdout.getvalue().startswith('original\noriginal\n'))
        self.assertEqual(len(set(directories)),2);self.assertTrue(all(not d.exists() for d in directories))

    def test_startup_or_malformed_worker_output_never_passes(self):
        file=self.source('one.zzy','(spec) "one" {}')
        for effect in (OSError('startup'),AssertionError('capture'),(0,b'',b'not json')):
            policy=ResourcePolicy();output=Output(io.StringIO(),io.StringIO(),ResourceMeter(policy,Phase.FRONTEND),'json')
            kwargs={'side_effect':effect} if isinstance(effect,Exception) else {'return_value':effect}
            with patch('zzy.spec_runner.run_bounded',**kwargs):status=run_specs(file,output,policy,10)
            self.assertEqual(status,1)
            self.assertEqual(json.loads(output.stdout.getvalue())['failed'],1)
            self.assertEqual(json.loads(output.stderr.getvalue())['code'],'E401')

    def test_collection_snapshot_total_limit_is_not_per_file(self):
        self.source('a.zzy','(spec) "a" {}')
        self.source('b.zzy','(spec) "b" {}')
        config=self.source('limits.json','{"policy_version":1,"limits":{"source_total_bytes":20}}')
        records=self.summary(self.cli('test',self.root,'--limits',config),dict(tests=1,passed=0,failed=0,timed_out=0,collection_errors=1))
        self.assertEqual(records[0]['code'],'E211')
