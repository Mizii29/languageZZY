"""Host-only state and allocation probes supplement independent CLI fixtures."""
from fractions import Fraction
import unittest
from unittest.mock import patch

from tests.test_interpreter import prepared
from zzy.diagnostics import Cancelled, DiagnosticError, ResourceExceeded
from zzy.interpreter import Interpreter
from zzy.values import WakeRequest, freeze


class P04RuntimeTests(unittest.TestCase):
    def released(self, runtime):
        self.assertIsNone(runtime.frame)
        self.assertIsNone(runtime.current_item)
        self.assertEqual(runtime.call_depth, 0)
        self.assertFalse(runtime.bindings)
        for key in ('runtime_objects', 'runtime_slots', 'runtime_payload_bytes'):
            self.assertEqual(runtime.meter.used(key), 0, key)

    def test_lazy_cached_error_preserves_origin_and_fresh_wake_note(self):
        program, output = prepared('(zyes)n:=0;(addnew) bad(){n<-n+1;(return)1/0;}'
                                   '(zno)v:=(zzz)(bad());\nio.print("probe");\nio.print("probe2");')
        runtime = Interpreter(program, output)
        lazy_node = program.root.children[2]
        calls = [n.children[0] for n in program.root.children[3:]]
        diagnostics = []
        def inspect(text):
            lazy = runtime.bindings[id(lazy_node)].value
            node = calls[len(diagnostics)]
            with self.assertRaises(DiagnosticError) as caught:
                runtime.drive(runtime.execute_lazy(WakeRequest(lazy, node)))
            diagnostics.append(caught.exception.diagnostic)
            self.assertEqual(lazy.state, 'FAILED')
            self.assertEqual(runtime.bindings[id(program.root.children[0])].value.data, 1)
            self.assertIsNone(runtime.frame)
            self.assertEqual(runtime.call_depth, 0)
        with patch.object(output, 'write', inspect):
            runtime.run()
        self.assertEqual(diagnostics[0].code, 'E205')
        self.assertEqual(diagnostics[0].span, diagnostics[1].span)
        self.assertEqual(diagnostics[0].notes[:-1], diagnostics[1].notes[:-1])
        self.assertNotEqual(diagnostics[0].notes[-1], diagnostics[1].notes[-1])
        self.released(runtime)

    def test_lazy_abort_resets_new_and_retry_evaluates(self):
        for failure in (Cancelled, MemoryError, ResourceExceeded):
            with self.subTest(failure=failure):
                program, output = prepared('(zno)v:=(zzz)(3);io.print("probe");')
                runtime = Interpreter(program, output)
                node = program.root.children[0]
                original = runtime.evaluate
                def inspect(text):
                    lazy = runtime.bindings[id(node)].value
                    def injected(expression):
                        if expression is node.children[0].children[0]:
                            if failure is ResourceExceeded:
                                runtime.check('runtime_slots', 10**9, expression)
                            raise failure()
                        return (yield from original(expression))
                    with patch.object(runtime, 'evaluate', injected):
                        with self.assertRaises(failure):
                            runtime.drive(runtime.execute_lazy(WakeRequest(lazy, node)))
                    self.assertEqual((lazy.state,lazy.cached), ('NEW',None))
                    self.assertIsNone(runtime.frame)
                    self.assertEqual(runtime.call_depth,0)
                    value=runtime.drive(runtime.execute_lazy(WakeRequest(lazy,node)))
                    self.assertEqual(value.data,3)
                    self.assertEqual(lazy.state,'READY')
                with patch.object(output,'write',inspect):runtime.run()
                self.released(runtime)

    def test_machine_result_allocation_failure_does_not_commit_state(self):
        program, output=prepared('(machine) M {a -- "go" --> b;}(zno)p:=M("a");p<<"go";')
        runtime=Interpreter(program,output)
        observed=[]
        original=runtime.result
        def fail(success,payload,node):
            machine=runtime.bindings[id(program.root.children[1])].value
            observed.append(machine)
            runtime.check('runtime_slots',10**9,node)
            return original(success,payload,node)
        with patch.object(runtime,'result',fail):
            with self.assertRaises(ResourceExceeded):runtime.run()
        self.assertEqual(observed[0].data[1].data,'a')
        self.released(runtime)

    def test_recursive_freeze_blocks_machine_array_and_shape_writes(self):
        prefix='(machine) M {a -- "go" --> b;}(shape) Box {items:(Array);}(zno)p:=M("a");(zno)b:=Box::{items:[p]};io.print("freeze");'
        for action in ('p<<"go";','array.push(b.items,1);','b.items[0]<-M("a");','b.items<-[];'):
            with self.subTest(action=action):
                program,output=prepared(prefix+action)
                runtime=Interpreter(program,output)
                def lock(text):freeze(runtime.bindings[id(program.root.children[3])].value,runtime,program.root)
                with patch.object(output,'write',lock):
                    with self.assertRaises(DiagnosticError) as caught:runtime.run()
                self.assertEqual(caught.exception.diagnostic.code,'E203')
                self.released(runtime)

    def test_query_phase_order_counts_and_snapshot_aliases(self):
        program,output=prepared('(zno)a:=[[2],[1],[2]];(zno)b:=a ?> {(keep):@[0]>0;(order):@[0] (desc);(take):2;(yield):@;};io.print("probe");')
        runtime=Interpreter(program,output)
        query=program.root.children[1].children[0]
        names={id(c.children[0]):c.kind for c in query.children[1:]}
        events=[]
        original=runtime.evaluate
        def evaluate(node):
            if id(node) in names:events.append(names[id(node)])
            return (yield from original(node))
        def inspect(text):
            a=runtime.bindings[id(program.root.children[0])].value
            b=runtime.bindings[id(program.root.children[1])].value
            self.assertIsNot(a,b)
            self.assertIs(b.data[0],a.data[0]);self.assertIs(b.data[1],a.data[2])
            self.assertEqual(a.active,0)
        with patch.object(runtime,'evaluate',evaluate),patch.object(output,'write',inspect):runtime.run()
        self.assertEqual(events,['take']+['keep']*3+['order']*3+['yield']*2)
        self.released(runtime)

    def test_query_exception_restores_current_and_reservations(self):
        for source in ('[1,0] ?> {(keep):1/@>0;(yield):@;};',
                       '[1,0] ?> {(order):1/@;(yield):@;};',
                       '[1,0] ?> {(yield):1/@;};'):
            program,output=prepared(source);runtime=Interpreter(program,output)
            with self.assertRaises(DiagnosticError) as caught:runtime.run()
            self.assertEqual(caught.exception.diagnostic.code,'E205')
            self.assertIn('查询输入下标 1',caught.exception.diagnostic.notes)
            self.released(runtime)

    def test_context_reuse_resets_machine_lazy_query_and_cells(self):
        program,output=prepared('(machine) M {a -- "go" --> b;}(zno)p:=M("a");(zyes)n:=0;'
            '(addnew) next(){n<-n+1;(return)n;}(zno)v:=(zzz)(next());'
            'io.print(p<<"go");io.print(wake(v));io.print([2,1] ?> {(order):@;(yield):@;});')
        runtime=Interpreter(program,output)
        for _ in range(3):runtime.run();self.released(runtime)
        Interpreter(program,output).run()
        self.assertEqual(output.stdout.getvalue(),'(^_^)(b)\n1\n[1, 2]\n'*4)
        with self.assertRaises(TypeError):program.machines[0]=None
        with self.assertRaises(TypeError):next(iter(program.machines.values()))[0][('a','go')]='c'

    def test_quantity_fraction_reference_and_intermediate_limits(self):
        program,output=prepared('io.print((0.125::s+1::s/7)*3);io.print(1::s*0.1);')
        runtime=Interpreter(program,output);runtime.run()
        expected=(Fraction(1,8)+Fraction(1,7))*3
        binary=Fraction(0.1)
        self.assertEqual(output.stdout.getvalue(),f'{expected}::s\n{binary}::s\n')
        self.released(runtime)
        # Each operand/result fits; comparison cross-products require six bits.
        for bits,ok in ((4,False),(5,False),(6,True)):
            program,output=prepared('io.print(7::s/3 < 5::s/7);',{'integer_bits':bits})
            runtime=Interpreter(program,output)
            if ok:runtime.run();self.assertEqual(output.stdout.getvalue(),'false\n')
            else:
                with self.assertRaises(ResourceExceeded):runtime.run()
            self.released(runtime)

    def test_quantity_exponent_boundaries_and_denominator(self):
        for limit,ok in ((1,False),(2,True),(3,True)):
            program,output=prepared('io.print(1::m*1::m);',{'quantity_exponent_abs':limit})
            runtime=Interpreter(program,output)
            if ok:runtime.run();self.assertEqual(output.stdout.getvalue(),'1::m^2\n')
            else:
                with self.assertRaises(ResourceExceeded):runtime.run()
            self.released(runtime)
        with self.assertRaises(ResourceExceeded):prepared('0.1::s;',{'integer_bits':3})
        program,output=prepared('0.1::s;',{'integer_bits':4});Interpreter(program,output).run()

    def test_lazy_call_depth_is_shared_with_functions(self):
        source='(addnew) f(n){(zif?:) n==0 {(return)1;}(return)wake((zzz)(f(n-1)));}io.print(f(3));'
        for limit,ok in ((6,False),(7,True),(8,True)):
            program,output=prepared(source,{'call_depth':limit});runtime=Interpreter(program,output)
            if ok:runtime.run();self.assertEqual(output.stdout.getvalue(),'1\n')
            else:
                with self.assertRaises(ResourceExceeded):runtime.run()
            self.released(runtime)

    def test_query_abort_signals_release_and_reset_current(self):
        for failure in (Cancelled,MemoryError,ResourceExceeded):
            program,output=prepared('[1,2] ?> {(order):@;(yield):@;};')
            runtime=Interpreter(program,output)
            query=program.root.children[0].children[0]
            projection=query.children[-1].children[0]
            original=runtime.evaluate
            def injected(node):
                if node is projection:
                    if failure is ResourceExceeded:runtime.check('runtime_slots',10**9,node)
                    raise failure()
                return (yield from original(node))
            with patch.object(runtime,'evaluate',injected):
                with self.assertRaises(failure):runtime.run()
            self.released(runtime)

    def test_freeze_reaches_machine_inside_result_and_cycles(self):
        program,output=prepared('(machine) M {a -- "go" --> b;}(zno)p:=M("a");'
            '(zno)a:=[(^_^)(p)];array.push(a,a);io.print("freeze");p<<"go";')
        runtime=Interpreter(program,output)
        def lock(text):freeze(runtime.bindings[id(program.root.children[2])].value,runtime,program.root)
        with patch.object(output,'write',lock):
            with self.assertRaises(DiagnosticError) as caught:runtime.run()
        self.assertEqual(caught.exception.diagnostic.code,'E203')
        self.released(runtime)
