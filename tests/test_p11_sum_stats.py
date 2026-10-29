"""Real CLI fixed sum/stats answers plus item order, quota and cancellation."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.test_interpreter import prepared
from zzy.diagnostics import Cancelled,DiagnosticError
from zzy.interpreter import Interpreter
from zzy.output import Output
from zzy.resources import ResourceMeter,ResourcePolicy
from zzy.diagnostics import Phase


class WatchingInterpreter(Interpreter):
    def __init__(self,*args,stop=None,**kwargs):
        super().__init__(*args,**kwargs);self.pairs=[];self.stop=stop
    def integer_operation(self,operation,a,b,node):
        if operation=='PLUS':
            self.pairs.append((a,b))
            if len(self.pairs)==self.stop:self.meter.cancellation.cancel()
        return super().integer_operation(operation,a,b,node)


class SumStatsTests(unittest.TestCase):
    def cli(self,source,limits=None):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);file=p/'case.zzy';file.write_text(source,encoding='utf-8')
            cmd=[sys.executable,'-X','utf8','-m','zzy','run',str(file),'--diagnostic-format','json']
            if limits:
                config=p/'limits.json';config.write_text(json.dumps({'policy_version':1,'limits':limits}))
                cmd+=['--limits',str(config)]
            r=subprocess.run(cmd,capture_output=True,timeout=10)
            return r.returncode,r.stdout.decode(),r.stderr.decode()

    def test_fixed_cli_answers_empty_signed_duplicates_and_input_alias(self):
        for literal,total,stats in [('[]',0,[0,0,None,None]),('[5]',5,[1,5,5,5]),('[-5,10,-5]',0,[3,0,-5,10]),('[2,2,1]',5,[3,5,1,2]),('[-9,-2,-9]',-20,[3,-20,-9,-2])]:
            source=f'(zno)a:={literal};(zno)alias:=a;io.print(array.sum(a));(zno)s:=array.stats(a);io.print([s.count,s.sum,s.min,s.max]);(o_o)alias==a;io.print(a);'
            code,out,err=self.cli(source)
            self.assertEqual((code,err),(0,''))
            self.assertEqual(out,str(total)+'\n'+json.dumps(stats)+'\n'+json.dumps(json.loads(literal))+'\n')

    def test_real_cli_midway_types_and_partial_sum_overflow(self):
        for function in ('sum','stats'):
            for item in ('(true)','"x"','1.5'):
                source=f'array.{function}([1,{item},2]);'
                code,out,err=self.cli(source);record=json.loads(err)
                self.assertEqual((code,out,record['code']),(1,'','E201'))
                self.assertEqual(record['span'],{'start':{'line':1,'column':source.index('[')+1},'end':{'line':1,'column':source.index(']')+2}})
            source=f'array.{function}([127,127,127,-127,-127,-127]);'
            code,out,err=self.cli(source,{'integer_bits':8});record=json.loads(err)
            self.assertEqual((code,out,record['code']),(1,'','E211'))
            self.assertEqual(record['message'],'资源超限：integer_bits，上限 8，本次需求 9')
            self.assertEqual(record['span'],{'start':{'line':1,'column':source.index('(')+1},'end':{'line':1,'column':source.index('(')+2}})
        self.assertEqual(self.cli('io.print(array.sum([127,127,-127,-127]));',{'integer_bits':8})[:2],(0,'0\n'))

    def test_checks_and_additions_remain_interleaved(self):
        for function in ('sum','stats'):
            program,out=prepared(f'array.{function}([1,2,(true),4]);')
            r=WatchingInterpreter(program,out)
            with self.assertRaises(DiagnosticError):r.run()
            self.assertEqual(r.pairs,[(0,1),(1,2)])
            self.assertTrue(all(r.meter.used(k)==0 for k in ('runtime_slots','runtime_objects','runtime_payload_bytes')))

    def test_midway_cancel_cleanup_and_following_context_recovery(self):
        for function in ('sum','stats'):
            program,out=prepared(f'(zno)a:=[1,2,3];array.{function}(a);io.print(a);')
            r=WatchingInterpreter(program,out,stop=2)
            with self.assertRaises(Cancelled):r.run()
            self.assertEqual(r.pairs,[(0,1),(1,2)])
            self.assertIsNone(r.frame);self.assertFalse(r.bindings)
            self.assertTrue(all(r.meter.used(k)==0 for k in ('runtime_slots','runtime_objects','runtime_payload_bytes')))
            fresh=Output(io.StringIO(),io.StringIO(),ResourceMeter(ResourcePolicy(),Phase.EXECUTION))
            next_run=WatchingInterpreter(program,fresh);next_run.run()
            self.assertEqual(next_run.pairs,[(0,1),(1,2),(3,3)])
            self.assertEqual(fresh.stdout.getvalue(),'[1, 2, 3]\n')


if __name__=='__main__':unittest.main()
