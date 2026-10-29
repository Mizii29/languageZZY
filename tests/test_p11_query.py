"""Full-query fixed answers and generic-comparator equivalence, including cancellation."""
import inspect
import io
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.test_interpreter import prepared
from zzy.diagnostics import Cancelled,DiagnosticError,ResourceExceeded,Phase
from zzy.interpreter import Interpreter
from zzy.output import Output
from zzy.resources import ResourcePolicy,ResourceMeter


class GenericSort(Interpreter):
    def _query_comparator(self,category,expression):
        def compare(a,b):
            self.meter.cancellation.check()
            if self.binary('LESS',a[1],b[1],expression).data:return -1
            if self.binary('GREATER',a[1],b[1],expression).data:return 1
            return 0
        return compare


class CountingSort(Interpreter):
    def __init__(self,*args):super().__init__(*args);self.comparisons=[]
    def binary(self,operation,left,right,node):
        if operation in {'LESS','GREATER'}:self.comparisons.append((left.kind,right.kind))
        return super().binary(operation,left,right,node)


def query_source(keys,direction):
    values=','.join(f'[{key},{i}]' for i,key in enumerate(keys))
    return f'(zno)a:=[{values}];io.print(a ?>{{(order):@[0]({direction});(yield):@[1];}});io.print(a ?>{{(yield):@[1];}});'


class QueryComparatorTests(unittest.TestCase):
    def execute(self,source,klass=Interpreter,limits=None,stop_sort=None):
        program,out=prepared(source);out.meter.policy=ResourcePolicy(limits or {})
        r=klass(program,out);sentinel=object();r.current_item=sentinel;sort_calls=[]
        if stop_sort:
            check=r.meter.cancellation.check
            def cancel_in_comparator():
                if inspect.currentframe().f_back.f_code.co_name=='compare':
                    sort_calls.append(True)
                    if len(sort_calls)==stop_sort:raise Cancelled()
                check()
            r.meter.cancellation.check=cancel_in_comparator
        try:r.run();answer=('ok',out.stdout.getvalue())
        except ResourceExceeded as e:answer=('quota',e.key,e.limit,e.requested,e.phase,e.diagnostic.record())
        except DiagnosticError as e:answer=('error',e.phase,e.diagnostic.record())
        except Cancelled:answer=('cancelled',)
        self.assertIs(r.current_item,sentinel);self.assertIsNone(r.frame);self.assertFalse(r.bindings)
        self.assertTrue(all(r.meter.used(k)==0 for k in ('runtime_slots','runtime_objects','runtime_payload_bytes')))
        return answer,r,sort_calls

    def test_fixed_real_cli_stable_mixed_numbers_strings_quantities_and_input(self):
        cases=[(['9007199254740993','9007199254740992.0','9007199254740992','1.0','1'],[3,4,1,2,0],[0,1,2,3,4]),(['"中"','"😀"','"a"','"A"','"a"'],[3,2,4,0,1],[1,0,2,4,3]),(['1::m','100::cm','2::m','1::cm'],[3,0,1,2],[2,0,1,3])]
        cases.append((['-9007199254740993','-9007199254740992.0','-9007199254740992','-0.0','0','0.0'],[0,1,2,3,4,5],[3,4,5,1,2,0]))
        for keys,asc,desc in cases:
            for direction,answer in [('asc',asc),('desc',desc)]:
                source=query_source(keys,direction);expected=json.dumps(answer)+'\n'+json.dumps(list(range(len(keys))))+'\n'
                self.assertEqual(self.execute(source)[0],('ok',expected))
                self.assertEqual(self.execute(source,GenericSort)[0],('ok',expected))
                with tempfile.TemporaryDirectory() as directory:
                    p=Path(directory)/'query.zzy';p.write_text(source,encoding='utf-8')
                    result=subprocess.run([sys.executable,'-X','utf8','-m','zzy','run',str(p)],capture_output=True,timeout=10)
                    self.assertEqual((result.returncode,result.stdout.decode(),result.stderr),(0,expected,b''))

    def test_specialization_and_quantity_generic_route(self):
        for keys,want in [(['3','1.5','2'],False),(['"b"','"a"','"c"'],False),(['3::m','1::m','2::m'],True)]:
            _,r,_=self.execute(query_source(keys,'asc'),CountingSort)
            self.assertEqual(bool(r.comparisons),want)
            if want:self.assertTrue(all(kinds==('Quantity','Quantity') for kinds in r.comparisons))

    def test_empty_filter_take_boundaries_and_shallow_alias(self):
        cases=[('io.print([] ?>{(order):1/0;(take):0;(yield):1/0;});','[]\n'),('io.print([2,1] ?>{(keep):(false);(order):1/0;(take):9;(yield):1/0;});','[]\n'),('io.print([3,1,2] ?>{(order):@;(take):0;(yield):1/0;});','[]\n'),('io.print([3,1,2] ?>{(order):@;(take):9;(yield):@;});','[1, 2, 3]\n'),('(zno)a:=[[2,0],[1,1]];(zno)b:=a ?>{(order):@[0];(yield):@;};b[0][0]<-99;io.print(a[1][0]);','99\n')]
        for source,expected in cases:
            self.assertEqual(self.execute(source)[0],('ok',expected))
            self.assertEqual(self.execute(source,GenericSort)[0],('ok',expected))

    def test_late_invalid_key_and_original_input_note_even_when_take_zero(self):
        cases=[('io.print([1,(true)] ?>{(order):@;(take):0;(yield):@;});','E201'),('io.print([1::m,1::s] ?>{(order):@;(take):0;(yield):@;});','E213'),('io.print([2,1,0] ?>{(keep):@<2;(order):1/@;(take):0;(yield):@;});','E205'),('io.print([2,1] ?>{(order):1/0;(take):-1;(yield):@;});','E208')]
        for source,code in cases:
            actual=self.execute(source)[0]
            self.assertEqual(actual,self.execute(source,GenericSort)[0])
            self.assertEqual(actual[0],'error');self.assertEqual(actual[2]['code'],code)
            if code=='E205':self.assertEqual(actual[2]['notes'],['查询输入下标 2'])

    def test_sort_workspace_quotas_and_current_item_cleanup_match_generic(self):
        source='io.print([5,1,4,2,3] ?>{(order):@;(take):0;(yield):@;});'
        outcomes=[]
        for limit in range(1,45):
            actual=self.execute(source,limits={'runtime_slots':limit})[0]
            self.assertEqual(actual,self.execute(source,GenericSort,{'runtime_slots':limit})[0])
            outcomes.append(actual[0])
        self.assertIn('quota',outcomes);self.assertIn('ok',outcomes)

    def test_actual_sort_cancellation_and_next_context_recovery(self):
        for keys in (['5','1','4','2','3'],['"e"','"a"','"d"','"b"','"c"'],['5::m','1::m','4::m','2::m','3::m']):
            source=query_source(keys,'asc')
            for klass in (Interpreter,GenericSort):
                answer,_,calls=self.execute(source,klass,stop_sort=3)
                self.assertEqual(answer,('cancelled',));self.assertEqual(len(calls),3)
            self.assertEqual(self.execute(source)[0],('ok','[1, 3, 4, 2, 0]\n[0, 1, 2, 3, 4]\n'))

    def test_shared_program_interleaved_queries_keep_inputs_and_state_private(self):
        source='(zno)p:=io.input("");(zno)a:=[[2,p+"B"],[1,p+"A"]];io.print(a ?>{(order):@[0];(yield):@[1];});'
        program,_=prepared(source);barrier=Barrier(4)
        class InterleavedSort(Interpreter):
            def _query_comparator(self,category,expression):
                # All contexts have finished key evaluation before any sort.
                barrier.wait(timeout=5)
                return super()._query_comparator(category,expression)
        def request(index):
            meter=ResourceMeter(ResourcePolicy(),Phase.EXECUTION)
            output=Output(io.StringIO(),io.StringIO(),meter)
            r=InterleavedSort(program,output,io.StringIO(f"request{index}\n"))
            r.run()
            self.assertIsNone(r.current_item);self.assertFalse(r.bindings)
            self.assertTrue(all(meter.used(k)==0 for k in ('runtime_slots','runtime_objects','runtime_payload_bytes')))
            return output.stdout.getvalue()
        with ThreadPoolExecutor(max_workers=4) as pool:answers=list(pool.map(request,range(4)))
        self.assertEqual(answers,[f'[request{i}A, request{i}B]\n' for i in range(4)])


if __name__=='__main__':unittest.main()
