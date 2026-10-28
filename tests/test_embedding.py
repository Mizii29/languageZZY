"""Public embedding acceptance using real ZZY, detached data and owned contexts."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from zzy.embedding import load_module, ConversionError, _CallRuntime
from zzy.diagnostics import DiagnosticError, ResourceExceeded, Cancelled
from zzy.resources import ResourcePolicy, CancellationToken

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT/'tests/p08/embed.zzy'


@contextmanager
def released(test):
    original = _CallRuntime.run
    runs = []
    def checked(runtime):
        try:
            return original(runtime)
        finally:
            test.assertFalse(runtime.bindings)
            test.assertFalse(runtime.modules)
            test.assertFalse(runtime.native_active)
            for key in ('runtime_objects', 'runtime_slots', 'runtime_payload_bytes'):
                test.assertEqual(runtime.meter.used(key), 0, key)
            runs.append(True)
    with patch.object(_CallRuntime, 'run', checked):
        yield runs


class EmbeddingTests(unittest.TestCase):
    def test_exact_scalar_and_nested_roundtrip(self):
        values = [None, True, False, 1, -1, 1.5, -0.0, 2**20000,
                  '中文😀[OoO]n', [], {}, {'a':[True,1,None,{'b':'x'}]}]
        with load_module(FIXTURE) as module, released(self):
            for value in values:
                result = module.call('identity', value)
                self.assertEqual(result.value, value)
                self.assertIs(type(result.value), type(value))
                self.assertEqual((result.stdout,result.stderr), ('',''))
            self.assertEqual(module.call('add',2,3).value,5)
            self.assertEqual(module.call('shape_value').value,{'value':[1,True,None]})

    def test_detached_copies_and_alias_policy(self):
        original = [1]
        with load_module(FIXTURE) as module:
            self.assertEqual(module.call('mutate',original).value,[1,9])
            self.assertEqual(original,[1])
            self.assertEqual(module.call('aliases',[original,original]).value,[[1,9],[1]])
            result = module.call('repeated_value').value
            self.assertIsNot(result[0],result[1])
            result[0].append(9)
            self.assertEqual(result,[[1,9],[1]])
        self.assertEqual(result[1],[1])  # Usable after module and context release.

    def test_rejects_python_types_cycles_and_invalid_numbers(self):
        class Foreign:
            def __str__(self): raise AssertionError('no conversion hook')
        class ListSubclass(list):
            def __iter__(self): raise AssertionError('no iteration hook')
        cycle=[];cycle.append(cycle)
        map_cycle={};map_cycle['self']=map_cycle
        bad=[Foreign(),ListSubclass(),(1,),b'x',{1:'x'},{True:'x'},cycle,map_cycle,
             float('nan'),float('inf'),-float('inf'),'\ud800',{'\udfff':1}]
        with load_module(FIXTURE) as module, released(self):
            for value in bad:
                with self.subTest(type=type(value)),self.assertRaises(ConversionError):
                    module.call('identity',value)
            self.assertEqual(module.call('identity',1).value,1)

    def test_rejects_zzy_values_without_waking_or_unpacking(self):
        from zzy.output import Output
        emitted=[];original=Output.write
        def observed(output,text,**kwargs):
            emitted.append(text);return original(output,text,**kwargs)
        names=['lazy','result','function','native_function','machine','quantity','range',
               'native','definition','namespace','cycle','map_cycle']
        with load_module(FIXTURE) as module,released(self),patch.object(Output,'write',observed):
            for name in names:
                with self.subTest(name=name),self.assertRaises(ConversionError):
                    module.call(name+'_value')
            self.assertEqual(module.call('identity',7).value,7)
        self.assertEqual(emitted,[])
        self.assertNotIn('tkinter',sys.modules)

    def test_load_snapshot_no_execution_and_invalid_calls_before_initialization(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'module.zzy';effect=Path(directory)/'effect.txt'
            source=f'io.write_text("{effect.as_posix()}","ran"); (addnew) f(x) {{ (return) x; }}'
            p.write_text(source,encoding='utf-8')
            with load_module(p) as module:
                self.assertFalse(effect.exists());self.assertEqual(module.exports,('f',))
                for name,args,error in [('missing',(),LookupError),('f',(),TypeError),('f',(object(),),ConversionError)]:
                    with self.assertRaises(error):module.call(name,*args)
                    self.assertFalse(effect.exists())
                p.write_text('(addnew) f(x) { (return) 999; }',encoding='utf-8')
                self.assertEqual(module.call('f',5).value,5)
                self.assertEqual(effect.read_text(),'ran')
            with load_module(p) as module:self.assertEqual(module.call('f',5).value,999)

    def test_diagnostics_and_recovery(self):
        with load_module(FIXTURE) as module,released(self):
            with self.assertRaises(DiagnosticError) as caught:module.call('add',True,1)
            diagnostic=caught.exception.diagnostic
            self.assertEqual(diagnostic.code,'E201');self.assertEqual(diagnostic.span.start.line,5)
            with self.assertRaises(DiagnosticError) as caught:module.call('boom')
            self.assertEqual(caught.exception.diagnostic.code,'E205')
            self.assertEqual(caught.exception.diagnostic.span.start.line,10)
            self.assertTrue(caught.exception.diagnostic.notes)
            self.assertEqual(module.call('add',1,2).value,3)

    def test_resource_limits_input_output_and_cleanup(self):
        deep=1
        for _ in range(64):deep=[deep]
        with load_module(FIXTURE) as module,released(self):
            self.assertEqual(module.call('identity',deep).value,deep)
            with self.assertRaises(ResourceExceeded):module.call('identity',[deep])
        with load_module(FIXTURE,policy=ResourcePolicy({'value_depth':2})) as module,released(self):
            self.assertEqual(module.call('identity',[[1]]).value,[[1]])
            with self.assertRaises(ResourceExceeded):module.call('identity',[[[1]]])
        for key,at,over in [('container_items',[1,2],[1,2,3]),('integer_bits',3,8),('text_codepoints','ab','abc')]:
            with load_module(ROOT/'tests/p08/embed-boundary.zzy',policy=ResourcePolicy({key:2})) as module,released(self):
                self.assertEqual(module.call('identity',at).value,at)
                with self.assertRaises(ResourceExceeded) as caught:module.call('identity',over)
                self.assertEqual(caught.exception.key,key)
        with load_module(FIXTURE,policy=ResourcePolicy({'runtime_slots':200})) as module,released(self):
            with self.assertRaises(ResourceExceeded):module.call('expanded_value')
        with load_module(FIXTURE,policy=ResourcePolicy({'io_payload_bytes':2})) as module,released(self):
            with self.assertRaises(ResourceExceeded):module.call('identity',1,stdin='abc')
        with load_module(FIXTURE,policy=ResourcePolicy({'stdout_bytes':2})) as module,released(self):
            with self.assertRaises(ResourceExceeded):module.call('state','abc')

    def test_dependency_snapshot_initialization_failure_and_api_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory);dep=directory/'dep.zzy';main=directory/'main.zzy'
            dep.write_text('(zyes) n := 0; (addnew) next() { n <- n+1; (return) n; }')
            main.write_text('(use) "dep.zzy" (as) dep; (addnew) next() { (return) dep.next(); }')
            with load_module(main) as module,released(self):
                dep.write_text('(addnew) next() { (return) 99; }')
                self.assertEqual(module.call('next').value,1)
                self.assertEqual(module.call('next').value,1)
                for kwargs in [{'stdin':None},{'cancellation':False}]:
                    with self.assertRaises(TypeError):module.call('next',**kwargs)
                with self.assertRaises(TypeError):module.call(None)
                with self.assertRaises(LookupError):module.call('dep.next')
            with self.assertRaises(TypeError):load_module(main,policy={})
            main.write_text('io.print(1/0); (addnew) next() { (return) 1; }')
            with load_module(main) as module,released(self):
                with self.assertRaises(DiagnosticError) as caught:module.call('next')
                self.assertEqual(caught.exception.diagnostic.code,'E205')
            main.write_text('(addnew) next() { (return) unknown; }')
            with self.assertRaises(DiagnosticError) as caught:load_module(main)
            self.assertEqual(caught.exception.diagnostic.code,'E302')

    def test_concurrent_io_state_and_active_close(self):
        barrier=threading.Barrier(2);entered=threading.Event();release=threading.Event()
        original=_CallRuntime.execute_program
        def interleaved(runtime):
            barrier.wait(5);entered.set()
            if not release.wait(5):raise AssertionError('barrier timed out')
            yield from original(runtime)
        module=load_module(FIXTURE)
        try:
            with patch.object(_CallRuntime,'execute_program',interleaved),ThreadPoolExecutor(2) as pool,released(self):
                calls=[pool.submit(module.call,'state',i,stdin=f'{i}\n') for i in range(2)]
                try:
                    self.assertTrue(entered.wait(5))
                    with self.assertRaises(RuntimeError):module.close()
                finally:release.set()
                for i,future in enumerate(calls):
                    result=future.result(5)
                    self.assertEqual(result.value,[1,str(i),i])
                    self.assertEqual(result.stdout,f'{i}\ninput> ')
            self.assertEqual(module.call('state',3).value,[1,None,3])
        finally:module.close()
        module.close()
        for operation in [lambda:module.call('identity',1),lambda:module.exports,module.__enter__]:
            with self.assertRaises(RuntimeError):operation()
        self.assertIsNone(module._program)

    def test_cancellation_and_next_call(self):
        token=CancellationToken();token.cancel()
        with load_module(FIXTURE) as module,released(self):
            with self.assertRaises(Cancelled):module.call('identity',1,cancellation=token)
            token=CancellationToken();timer=threading.Timer(.1,token.cancel);timer.start()
            try:
                with self.assertRaises(Cancelled):module.call('loop',cancellation=token)
            finally:timer.cancel();timer.join()
            self.assertEqual(module.call('identity',1).value,1)

    def test_example_cli_check_and_optional_import_isolation(self):
        check=subprocess.run([sys.executable,'-X','utf8','-m','zzy','check',str(FIXTURE)],capture_output=True)
        self.assertEqual((check.returncode,check.stdout,check.stderr),(0,b'',b''))
        demo=subprocess.run([sys.executable,'-X','utf8','-m','examples.web.embed'],cwd=ROOT,capture_output=True)
        self.assertEqual(demo.returncode,0,demo.stderr)
        self.assertEqual(json.loads(demo.stdout),{'status':200,'body':{'message':'你好，Ada'}})
        code="import zzy.embedding,sys; assert not any(n in sys.modules for n in ('starlette','uvicorn','tkinter','zzy.web'))"
        subprocess.run([sys.executable,'-c',code],cwd=ROOT,check=True)
