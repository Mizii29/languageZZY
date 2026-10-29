"""Fixed arithmetic answers and generic-route accounting/cancellation equivalence."""
import io
import random
import unittest
from unittest.mock import patch

from tests.test_p11_locations import runtime
from zzy.diagnostics import Cancelled,DiagnosticError,Phase,ResourceExceeded
from zzy.interpreter import Interpreter as ReleasedInterpreter
from benchmarks.p11_integer_candidate import SmallIntegerCandidate as Interpreter
from zzy.output import Output
from zzy.resources import ResourceMeter,ResourcePolicy
from zzy.values import Value


class GenericInterpreter(Interpreter):
    def _small_add_sub_bits(self,*args):return None


class TracedMeter(ResourceMeter):
    def __init__(self,limits,stop=None):
        super().__init__(ResourcePolicy(limits),Phase.EXECUTION)
        self.events=[];self.ticks=0;self.stop=stop
        self.cancellation.check=self.tick
    def tick(self):
        self.ticks+=1;self.events.append(('cancel',self.used('runtime_payload_bytes')))
        if self.ticks==self.stop:raise Cancelled()
    def check(self,key,requested,**where):
        self.events.append(('check',key,requested,self.used('runtime_payload_bytes')))
        return super().check(key,requested,**where)


class SmallIntegerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.program=runtime().program

    def run_op(self,klass,op,a,b,limits=None,stop=None):
        meter=TracedMeter(limits or {},stop)
        r=klass(self.program,Output(io.StringIO(),io.StringIO(),meter));node=self.program.root
        try:
            value=r.binary(op,Value('Int',a),Value('Int',b),node)
            answer=('value',value.kind,value.data)
            value.reservation.release()
        except ResourceExceeded as e:answer=('quota',e.key,e.limit,e.requested,e.phase,e.diagnostic.record())
        except Cancelled:answer=('cancelled',)
        self.assertEqual(meter.used('runtime_payload_bytes'),0)
        return answer,meter.events,meter.ticks

    def test_fixed_and_generated_signed_answers_match_generic(self):
        pairs=[(0,0),(1,1),(-1,1),(127,1),(255,1),(256,-1),(65535,1),(-255,-1),(8191,1),(8192,-8191)]
        rng=random.Random(1104)
        for bits in (1,7,8,9,15,16,17,23,24,25,30,31,63,128,4096):
            pairs.extend((rng.getrandbits(bits)*s,rng.getrandbits(bits)*t) for s,t in ((1,1),(-1,1),(1,-1),(-1,-1)))
        for a,b in pairs:
            for op in ('PLUS','MINUS'):
                with self.subTest(a=a,b=b,op=op):
                    actual=self.run_op(Interpreter,op,a,b)
                    self.assertEqual(actual,self.run_op(GenericInterpreter,op,a,b))
                    self.assertEqual(actual[0],('value','Int',a+b if op=='PLUS' else a-b))

    def test_all_cancellation_points_and_tight_quota_errors_are_identical(self):
        for a,b in ((0,0),(1,1),(127,-126),(255,1),(8191,1),(8192,8191),(-127,1),(-1,1),(2**128,1)):
            for op in ('PLUS','MINUS'):
                for limits in ({},{'integer_bits':7},{'integer_bits':8},{'runtime_payload_bytes':1},{'runtime_payload_bytes':2}):
                    baseline=self.run_op(GenericInterpreter,op,a,b,limits)
                    self.assertEqual(self.run_op(Interpreter,op,a,b,limits),baseline)
                    for stop in range(1,baseline[2]+1):
                        self.assertEqual(self.run_op(Interpreter,op,a,b,limits,stop),self.run_op(GenericInterpreter,op,a,b,limits,stop))

    def test_guard_is_conservative_and_fallback_has_no_side_effects(self):
        for a,b,limits,want in [(1,1,{},2),(8191,1,{},14),(255,1,{},None),(2**30,1,{},None),(127,-127,{},None),(127,-126,{'integer_bits':7},None),(1023,-1022,{'runtime_payload_bytes':1},None)]:
            meter=TracedMeter(limits);r=Interpreter(self.program,Output(io.StringIO(),io.StringIO(),meter))
            actual=r._small_add_sub_bits('PLUS',a,b,self.program.root)
            self.assertEqual(actual,want)
            self.assertEqual(meter.used('runtime_payload_bytes'),0)
            if want is None:self.assertEqual(meter.events,[])
        # Upper bound 8 must not reject an exact one-bit result under a 7-bit limit.
        self.assertEqual(self.run_op(Interpreter,'PLUS',127,-126,{'integer_bits':7})[0],('value','Int',1))

    def test_released_path_matches_fixed_candidate_answers(self):
        for a,b in ((127,1),(255,1),(8191,1),(63,126),(2**128-1,1)):
            for op in ('PLUS','MINUS'):
                self.assertEqual(self.run_op(ReleasedInterpreter,op,a,b),self.run_op(Interpreter,op,a,b))

    def test_actual_tags_float_promotion_and_unsupported_ops(self):
        base=runtime();r=Interpreter(base.program,base.output);node=r.program.root
        with patch.object(r,'_small_add_sub_bits',side_effect=AssertionError('must not enter Int guard')):
            with self.assertRaises(DiagnosticError) as e:r.binary('PLUS',Value('Bool',True),Value('Int',1),node)
            self.assertEqual(e.exception.diagnostic.code,'E201')
            value=r.binary('PLUS',Value('Float',1.5),Value('Int',2),node)
            self.assertEqual((value.kind,value.data),('Float',3.5));value.reservation.release()
            value=r.binary('MULTIPLY',Value('Int',3),Value('Int',7),node)
            self.assertEqual(value.data,21);value.reservation.release()


if __name__=='__main__':unittest.main()
