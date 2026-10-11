import gc
import io
import unittest
from unittest.mock import patch

from tests.test_interpreter import prepared
from zzy.diagnostics import Cancelled, DiagnosticError, ResourceExceeded
from zzy.interpreter import Interpreter
from zzy.values import Array, Cell, Frame, Value


class P03RuntimeTests(unittest.TestCase):
    def released(self, runtime):
        self.assertIsNone(runtime.frame)
        self.assertEqual(runtime.call_depth, 0)
        self.assertEqual(runtime.bindings, {})
        for key in ("runtime_objects", "runtime_slots", "runtime_payload_bytes"):
            self.assertEqual(runtime.meter.used(key), 0, key)

    def test_program_and_interpreter_reuse_have_fresh_cells_frames_and_arrays(self):
        source = ('(addnew) make() {(zyes) n:=0; (zno) a:=[]; '
                  '(addnew) f() {n<-n+1; array.push(a,n); (return) a;} (return) f;} '
                  '(zno) f:=make(); io.print(f()); io.print(f());')
        program, output = prepared(source)
        runtime = Interpreter(program, output)
        for _ in range(3):
            runtime.run()
            self.released(runtime)
        Interpreter(program, output).run()
        self.assertEqual(output.stdout.getvalue(), '[1]\n[1, 2]\n' * 4)
        for mapping in (program.symbols, program.functions, program.references, program.annotations):
            with self.assertRaises(TypeError):
                mapping[0] = None
        for plan in program.functions.values():
            with self.assertRaises(TypeError):
                plan.blocks[0] = ()

    def test_only_mutable_captures_use_cells_and_siblings_share_storage(self):
        program, output = prepared('(addnew) make(p) {(zyes) plain:=2; (zyes) x:=3; '
            '(zno) a:=[]; (addnew) f() {x<-x+1; (return) [p,a,x,plain];} '
            '(addnew) g() {(return) x;} (return) [f,g];} (zno) fs:=make(1); io.print(fs[0]());')
        observed = []
        original = Interpreter.make_function
        def remember(runtime, node):
            value = original(runtime, node)
            observed.append(value)
            return value
        with patch.object(Interpreter, 'make_function', remember):
            Interpreter(program, output).run()
        f, g = [v for v in observed if v.data.name in ('f', 'g')]
        self.assertIs(f.data.captures[0], g.data.captures[0])
        self.assertIsInstance(g.data.captures[0], Cell)
        self.assertEqual(sum(isinstance(v, Cell) for v in f.data.captures), 3)
        self.assertTrue(any(isinstance(v, Array) for v in f.data.captures))
        self.assertEqual(output.stdout.getvalue(), '[1, [], 4, 2]\n')

    def test_uncaptured_locals_are_direct_values(self):
        program, output = prepared('(addnew) f(p) {(zyes) x:=3; io.print(x+p);} f(2);')
        runtime = Interpreter(program, output)
        original = output.write
        def inspect(*args):
            self.assertEqual(len(runtime.frame.locals), 2)
            self.assertTrue(all(isinstance(v, Value) for v in runtime.frame.locals))
            return original(*args)
        with patch.object(output, 'write', inspect):
            runtime.run()
        self.released(runtime)

    def test_all_failure_paths_release_frames_and_active_iteration(self):
        for failure in (DiagnosticError, Cancelled, MemoryError, ResourceExceeded):
            with self.subTest(failure=failure):
                source = ('(zno) a:=[1]; (addnew) f(n) {(zyes) x:=n; '
                          '(zno) g:=(addnew) () => x; (for) v (in) a {'
                          '(zif?:) n>0 {f(n-1);} (zzyf:) {io.print(g());}}} f(8);')
                program, output = prepared(source)
                runtime = Interpreter(program, output)
                arrays, frames = [], []
                init_array, init_frame = Array.__init__, Frame.__init__
                def array(value, *args):
                    init_array(value, *args)
                    arrays.append(value)
                def frame(value, *args):
                    init_frame(value, *args)
                    frames.append(value)
                def fail(*args):
                    self.assertEqual(arrays[0].active, 9)
                    self.assertEqual(runtime.call_depth, 9)
                    if failure is DiagnosticError:
                        runtime.error(program.root, 'E205', 'injected')
                    if failure is ResourceExceeded:
                        runtime.check('runtime_slots', 10**9, program.root)
                    raise failure()
                with patch.object(Array, '__init__', array), patch.object(Frame, '__init__', frame), patch.object(output, 'write', fail):
                    try:
                        runtime.run()
                    except failure as error:
                        self.assertIsNotNone(error.__traceback__)
                        self.released(runtime)
                        if failure is ResourceExceeded:
                            self.assertEqual(len(error.diagnostic.notes), 9)
                            self.assertEqual(error.diagnostic.code, 'E211')
                        self.assertEqual(arrays[0].active, 0)
                        self.assertTrue(all(f.locals == [] and f.annotations == [] for f in frames))
                    else:
                        self.fail('injected failure was swallowed')

    def test_frame_allocation_failure_restores_parent_and_releases(self):
        program, output = prepared('(addnew) f() {} f();')
        runtime = Interpreter(program, output)
        with patch.object(Frame, '__init__', side_effect=MemoryError):
            with self.assertRaises(MemoryError):
                runtime.run()
        self.released(runtime)

    def test_dead_mutable_closure_cycles_do_not_exhaust_live_quota(self):
        # Each f -> Cell -> f cycle becomes unreachable at block exit.
        program, output = prepared('(for) i (in) 0..<50 {(zyes) f:=(null); '
                                   'f<-(addnew) () => f;} io.print("done");',
                                   {'runtime_objects': 4, 'runtime_slots': 12})
        runtime = Interpreter(program, output)
        runtime.run()
        gc.collect()
        self.released(runtime)
        self.assertEqual(output.stdout.getvalue(), 'done\n')

    def test_mutable_capture_write_retains_type_after_owner_returns(self):
        program, output = prepared('(addnew) make() {(zyes) x:(Int):=1; '
                                   '(addnew) set(v) {x<-v;} (return) set;} make()("bad");')
        runtime = Interpreter(program, output)
        with self.assertRaises(DiagnosticError) as caught:
            runtime.run()
        self.assertEqual(caught.exception.diagnostic.code, 'E201')
        self.released(runtime)

    def test_independent_contexts_share_no_runtime_values(self):
        program, output = prepared('(zyes) n:=0; (addnew) f() {n<-n+1; '
                                   '(return) io.input("")+str(n);} io.print(f());')
        for text in ('a\n','b\n'):
            runtime = Interpreter(program, output, io.StringIO(text))
            runtime.run()
            self.released(runtime)
        self.assertEqual(output.stdout.getvalue(), 'a1\nb1\n')

    def test_return_type_error_keeps_expression_span_and_call_notes(self):
        program, output = prepared('(addnew) f() -> (Int) {(return) "bad";}\nf();')
        runtime = Interpreter(program, output)
        with self.assertRaises(DiagnosticError) as caught:
            runtime.run()
        diagnostic = caught.exception.diagnostic
        self.assertEqual((diagnostic.span.start.line, diagnostic.span.start.column), (1, 33))
        self.assertEqual((diagnostic.span.end.line, diagnostic.span.end.column), (1, 38))
        self.assertEqual(diagnostic.notes, ('调用 f：test.zzy:2:2',))
        self.released(runtime)

    def test_nested_type_names_capture_transitively(self):
        program, output = prepared('(shape) S {} (addnew) a(T) {'
            '(addnew) b() {(addnew) c(x:T) -> T {(return) x;} (return) c;} '
            '(return) b;} io.print(a(S)()(S::{}));')
        runtime = Interpreter(program, output)
        runtime.run()
        self.assertEqual(output.stdout.getvalue(), 'S::{}\n')
        self.released(runtime)
