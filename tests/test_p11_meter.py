"""P11 reservation transactions, fault ownership and independent contexts."""
from concurrent.futures import ThreadPoolExecutor
import gc
import random
import unittest
from unittest.mock import patch
import weakref

from tests.test_p11_locations import runtime
from zzy.diagnostics import Cancelled,Phase,ResourceExceeded
from zzy.resources import ResourceMeter,ResourcePolicy,Reservation
from zzy.values import Array


class MeterOptimizationTests(unittest.TestCase):
    def test_registration_failure_releases_even_with_live_traceback(self):
        r=runtime();node=r.program.root
        for failure in (MemoryError('weak allocation'),Cancelled()):
            with patch.object(r.reservations,'add',side_effect=failure):
                try:r.reserve(node,runtime_slots=2,runtime_payload_bytes=3)
                except type(failure) as caught:
                    self.assertIsNotNone(caught.__traceback__)
                    self.assertEqual(r.meter.used('runtime_slots'),0)
                    self.assertEqual(r.meter.used('runtime_payload_bytes'),0)
                else:self.fail('missing injected failure')

    def test_validation_cancellation_order_and_multi_atomicity(self):
        meter=ResourceMeter(ResourcePolicy({'runtime_slots':3,'runtime_objects':2}),Phase.EXECUTION)
        with meter.reserve(runtime_slots=1,runtime_objects=1):
            for amounts,exception in [({'runtime_objects':1,'runtime_slots':3},ResourceExceeded),({'runtime_objects':1,'bogus':1},KeyError),({'runtime_objects':1,'runtime_slots':True},ValueError)]:
                before=dict(meter._used)
                with self.assertRaises(exception):meter.reserve(**amounts)
                self.assertEqual(meter._used,before)
            for slots in (1,2):
                with meter.reserve(runtime_slots=slots):self.assertEqual(meter.used('runtime_slots'),1+slots)
            with self.assertRaises(ResourceExceeded) as caught:meter.reserve(runtime_slots=3)
            self.assertEqual((caught.exception.key,caught.exception.limit,caught.exception.requested),('runtime_slots',3,4))
            meter.cancellation.cancel()
            # reserve rejects invalid amounts before check; check itself cancels first.
            with self.assertRaises(ValueError):meter.reserve(bogus=True)
            with self.assertRaises(Cancelled):meter.reserve(bogus=1)
            with self.assertRaises(Cancelled):meter.check('bogus',True)
            owner=meter.reserve();owner.release()  # originally no checks for empty reservation
        self.assertTrue(all(n==0 for n in meter._used.values()))

    def test_allocation_and_commit_faults_leave_no_partial_debit(self):
        class CopyFault(dict):
            def copy(self):raise MemoryError('copy')
        class AssignmentFault(dict):
            def __setitem__(self,key,value):raise MemoryError('single assignment')
        meter=ResourceMeter(ResourcePolicy(),Phase.EXECUTION)
        for amounts in ({'runtime_slots':2},{'runtime_slots':2,'runtime_objects':1}):
            with patch('zzy.resources.Reservation',side_effect=MemoryError('owner')):
                with self.assertRaises(MemoryError):meter.reserve(**amounts)
            self.assertEqual(meter.used('runtime_slots'),0)
        meter._used=CopyFault(runtime_slots=1,runtime_objects=2)
        with self.assertRaises(MemoryError):meter.reserve(runtime_slots=2,runtime_objects=1)
        self.assertEqual(meter._used,{'runtime_slots':1,'runtime_objects':2})
        meter._used=AssignmentFault(runtime_slots=1)
        with self.assertRaises(MemoryError):meter.reserve(runtime_slots=2)
        self.assertEqual(meter._used,{'runtime_slots':1})

    def test_release_weakrefs_subclass_cycles_aliases_and_gc_retry(self):
        r=runtime(runtime_objects=1);node=r.program.root
        a=Array(r,node);a.push(a,r,node)
        self.assertEqual((r.meter.used('runtime_objects'),r.meter.used('runtime_slots')),(1,1))
        ref=weakref.ref(a);del a
        # The next object reservation must still trigger cycle collection on overflow.
        b=Array(r,node);self.assertIsNone(ref())
        alias=b;del b;gc.collect()
        self.assertEqual(r.meter.used('runtime_objects'),1)
        del alias;gc.collect();self.assertEqual(r.meter.used('runtime_objects'),0)
        self.assertEqual(r.meter.used('runtime_slots'),0)
        class Child(Reservation):pass
        owner=Child(r.meter,{})
        owner.extra='subclass';reference=weakref.ref(owner)
        owner.release();owner.release();self.assertIs(reference(),owner)
        with self.assertRaises(MemoryError):
            with r.reserve(node,runtime_slots=2):raise MemoryError()
        self.assertEqual(r.meter.used('runtime_slots'),0)

    def test_random_reference_accounting_and_independent_concurrent_contexts(self):
        def exercise(seed):
            rng=random.Random(seed);meter=ResourceMeter(ResourcePolicy({'runtime_slots':17,'runtime_objects':11}),Phase.EXECUTION)
            owners=[];expected={'runtime_slots':0,'runtime_objects':0}
            for _ in range(100):
                if owners and rng.randrange(3)==0:
                    owner,amounts=owners.pop(0);owner.release();owner.release()
                    for key,n in amounts.items():expected[key]-=n
                else:
                    amounts={'runtime_slots':rng.randrange(7)}
                    if rng.randrange(2):amounts['runtime_objects']=rng.randrange(5)
                    excess=next(((key,expected[key]+n) for key,n in amounts.items() if expected[key]+n>meter.policy.limits[key]),None)
                    if excess:
                        with self.assertRaises(ResourceExceeded) as caught:meter.reserve(**amounts)
                        self.assertEqual((caught.exception.key,caught.exception.requested),excess)
                    else:
                        owners.append((meter.reserve(**amounts),amounts))
                        for key,n in amounts.items():expected[key]+=n
                self.assertEqual({k:meter.used(k) for k in expected},expected)
            for owner,_ in owners:owner.release()
            self.assertTrue(all(meter.used(k)==0 for k in expected))
            return meter
        with ThreadPoolExecutor(max_workers=4) as pool:meters=list(pool.map(exercise,range(12)))
        self.assertEqual(len({id(m) for m in meters}),12)


if __name__=='__main__':unittest.main()
