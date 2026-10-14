"""File failures, module snapshots and host invariants beyond fixed CLI fixtures."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.blackbox import ROOT
from tests.process import run_bounded
from tests.test_interpreter import prepared
from zzy.diagnostics import Cancelled, DiagnosticError, Phase, ResourceExceeded
from zzy.interpreter import Interpreter
from zzy.native import files
from zzy.native.catalog import FUNCTIONS, PURE_CALLS, REGISTRY
from zzy.output import Output
from zzy.prepare import prepare
from zzy.resources import ResourceMeter, ResourcePolicy
from zzy.source import SourceLoader
from zzy.spec_runner import run_specs
from zzy.values import freeze


def quote(text):
    return '"'+str(text).replace('[OoO]','[OoO][OoO]').replace('"','[OoO]q').replace('\n','[OoO]n')+'"'


class P05IntegrationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='ZZY P05 中文 ')
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)

    def source(self,name,text):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(text,encoding='utf-8');return path

    def cli(self,mode,file,*extra):
        return run_bounded([sys.executable,'-X','utf8','-m','zzy',mode,str(file),
            '--diagnostic-format','json',*map(str,extra)],cwd=self.root,
            env=dict(os.environ,PYTHONPATH=str(ROOT)),timeout=20)

    def output(self,limits=None):
        return Output(io.StringIO(),io.StringIO(),ResourceMeter(ResourcePolicy(limits or {}),Phase.FRONTEND),'json')

    def load(self,file,output):
        with SourceLoader(output.meter) as loader:
            return prepare(loader.read(file),output.meter,loader)

    def released(self,runtime):
        self.assertFalse(runtime.bindings);self.assertFalse(runtime.modules)
        self.assertIsNone(runtime.frame);self.assertEqual(runtime.call_depth,0)
        for key in ('runtime_slots','runtime_objects','runtime_payload_bytes'):
            self.assertEqual(runtime.meter.used(key),0,key)

    def test_files_real_cli_roundtrip_replace_and_relative_cwd(self):
        file=self.source('scripts/main.zzy','io.print(io.write_text("a.txt","旧[OoO]n"));'
            'io.print(io.read_text("a.txt"));io.print(io.write_atomic("a.txt","新😀"));'
            'io.print(io.write_text("b.txt","replacement"));io.print(io.replace_file("b.txt","a.txt"));'
            'io.print(io.read_text("a.txt"));')
        self.assertEqual(self.cli('run',file),(0,'(^_^)(null)\n(^_^)(旧\n)\n(^_^)(null)\n(^_^)(null)\n(^_^)(null)\n(^_^)(replacement)\n'.encode(),b''))
        self.assertEqual((self.root/'a.txt').read_bytes(),b'replacement')
        self.assertFalse((self.root/'b.txt').exists());self.assertFalse(list(self.root.glob('.zzy-*.tmp')))
        self.assertFalse((self.root/'scripts/a.txt').exists())

    def test_file_expected_failures_bom_and_outer_type(self):
        (self.root/'bad.txt').write_bytes(b'\xff')
        (self.root/'bom.txt').write_bytes(b'\xef\xbb\xbfhello')
        text='io.print(io.read_text("bom.txt"));'
        for call in ('io.read_text("bad.txt")','io.read_text("missing")','io.write_atomic("missing/target","x")','io.replace_file("missing","target")'):
            text+='(?_?)'+call+'{(T_T)(m)=>{io.print("failed");}_=>{io.print("wrong");}}'
        self.assertEqual(self.cli('run',self.source('read.zzy',text)),(0,'(^_^)(\ufeffhello)\nfailed\nfailed\nfailed\nfailed\n'.encode(),b''))
        result=self.cli('run',self.source('type.zzy','io.write_text("absent",1);'))
        self.assertEqual(result[0],1);self.assertEqual(json.loads(result[2])['code'],'E201')
        self.assertFalse((self.root/'absent').exists())

    def test_check_recursive_graph_does_not_touch_files_or_input(self):
        self.source('lib/side.zzy','io.input("must not prompt");io.write_text("must-not-exist","x");'
                    '(addnew) f(){(return)1/0;}(zno)x:=f();')
        file=self.source('main.zzy','(use) "lib/side.zzy" (as) m;io.write_atomic("target","changed");')
        (self.root/'target').write_bytes(b'old')
        self.assertEqual(self.cli('check',file),(0,b'',b''))
        self.assertEqual((self.root/'target').read_bytes(),b'old')
        self.assertFalse((self.root/'must-not-exist').exists())
        self.assertFalse(list(self.root.glob('.zzy-*.tmp')))

    def test_io_resource_boundary_is_diagnostic_and_preserves_atomic_target(self):
        for content,limit,status in [('中',3,0),('中',2,1)]:
            with self.subTest(limit=limit):
                (self.root/'target').write_bytes(b'old')
                limits=self.source('limits.json',json.dumps({'policy_version':1,'limits':{'io_payload_bytes':limit}}))
                file=self.source('atomic.zzy','io.print(io.write_atomic("target",'+quote(content)+'));')
                result=self.cli('run',file,'--limits',limits)
                self.assertEqual(result[0],status)
                self.assertEqual((self.root/'target').read_bytes(),content.encode() if status==0 else b'old')
                if status:self.assertEqual(json.loads(result[2])['code'],'E211')
        (self.root/'large').write_bytes('😀😀'.encode())
        limits=self.source('limits.json',json.dumps({'policy_version':1,'limits':{'text_codepoints':1}}))
        # Keep source literals within the same small text limit.
        (self.root/'x').write_bytes('😀😀'.encode())
        result=self.cli('run',self.source('read-limit.zzy','io.read_text("x");'),'--limits',limits)
        self.assertEqual(result[0],1);self.assertIn('text_codepoints',json.loads(result[2])['message'])

    def test_atomic_write_close_replace_failures_preserve_old_file_and_cleanup(self):
        target=self.root/'target';real_fdopen=files.os.fdopen
        for failure in ('write','close','replace'):
            with self.subTest(failure=failure):
                target.write_bytes(b'old')
                program,output=prepared('io.print(io.write_atomic('+quote(target)+',"new"));')
                runtime=Interpreter(program,output)
                class Stream:
                    def __init__(self,fd,mode):self.stream=real_fdopen(fd,mode)
                    def __enter__(self):return self
                    def write(self,raw):
                        if failure=='write':raise OSError('injected write')
                        return self.stream.write(raw)
                    def __exit__(self,*exc):
                        self.stream.close()
                        if failure=='close':raise OSError('injected close')
                with patch.object(files.os,'fdopen',Stream):
                    if failure=='replace':
                        with patch.object(files.os,'replace',side_effect=OSError('injected replace')):runtime.run()
                    else:runtime.run()
                self.assertTrue(output.stdout.getvalue().startswith('(T_T)(I/O failed:'))
                self.assertEqual(target.read_bytes(),b'old');self.assertFalse(list(self.root.glob('.zzy-*.tmp')))
                self.released(runtime)

    def test_atomic_abort_is_not_result_and_cleanup_is_guaranteed(self):
        target=self.root/'target'
        for failure in (Cancelled,MemoryError,ResourceExceeded):
            with self.subTest(failure=failure):
                target.write_bytes(b'old')
                program,output=prepared('io.write_atomic('+quote(target)+',"new");')
                runtime=Interpreter(program,output)
                def abort(*args):
                    if failure is ResourceExceeded:runtime.check('runtime_slots',10**9,program.root)
                    raise failure()
                with patch.object(files.os,'replace',side_effect=abort):
                    with self.assertRaises(failure):runtime.run()
                self.assertEqual(target.read_bytes(),b'old');self.assertFalse(list(self.root.glob('.zzy-*.tmp')))
                self.released(runtime)

    def test_atomic_concurrent_temp_names_are_exclusive(self):
        target=self.root/'target';target.write_bytes(b'old')
        programs=[prepared('io.write_atomic('+quote(target)+','+quote(x)+');') for x in ('outer','inner')]
        real_replace=files.os.replace;paths=[]
        def interleave(source,destination):
            paths.append(Path(source));self.assertTrue(Path(source).exists())
            self.assertEqual(Path(source).parent,target.parent)
            if len(paths)==1:Interpreter(*programs[1]).run()
            real_replace(source,destination)
        with patch.object(files.os,'replace',interleave):Interpreter(*programs[0]).run()
        self.assertEqual(len(set(paths)),2);self.assertEqual(target.read_bytes(),b'outer')
        self.assertFalse(list(self.root.glob('.zzy-*.tmp')))

    def test_program_module_reuse_fresh_state_and_dependency_reload(self):
        dependency=self.source('dep.zzy','(zyes)n:=0;(addnew) next(){n<-n+1;(return)n;}')
        entry=self.source('main.zzy','(use) "dep.zzy" (as) d;io.print(d.next());')
        output=self.output();program=self.load(entry,output)
        dependency.write_text('(addnew) next(){(return)99;}',encoding='utf-8')
        for _ in range(2):
            runtime=Interpreter(program,output);runtime.run();self.released(runtime)
        self.assertEqual(output.stdout.getvalue(),'1\n1\n')
        fresh=self.output();Interpreter(self.load(entry,fresh),fresh).run()
        self.assertEqual(fresh.stdout.getvalue(),'99\n')

    def test_import_limits_and_canonical_dedup(self):
        self.source('dep.zzy','(addnew) f(){(return)1;}')
        entry=self.source('main.zzy','(use) "dep.zzy" (as) a;(use) "./dep.zzy" (as) b;io.print(a==b);')
        for limits,expected in [({'module_count':2},0),({'module_count':1},2),({'import_depth':2},0),({'import_depth':1},2)]:
            config=self.source('limits.json',json.dumps({'policy_version':1,'limits':limits}))
            result=self.cli('run',entry,'--limits',config);self.assertEqual(result[0],expected)
            if expected:self.assertEqual(json.loads(result[2])['code'],'E211')
        total=sum(p.stat().st_size for p in (entry,self.root/'dep.zzy'))
        for size,expected in [(total,0),(total-1,2)]:
            config=self.source('limits.json',json.dumps({'policy_version':1,'limits':{'source_total_bytes':size}}))
            self.assertEqual(self.cli('check',entry,'--limits',config)[0],expected)

    def test_default_import_depth_boundary(self):
        for i in range(33):self.source(f'd{i}.zzy',f'(use) "d{i+1}.zzy" (as) d;' if i<32 else '')
        self.assertEqual(self.cli('check',self.root/'d1.zzy'),(0,b'',b''))
        result=self.cli('check',self.root/'d0.zzy')
        self.assertEqual(result[0],2);self.assertIn('import_depth',json.loads(result[2])['message'])

    def test_spec_modules_lazy_files_stdin_are_isolated_and_snapshotted(self):
        dependency=self.source('dep.zzy','(zyes)n:=0;(addnew) next(){n<-n+1;(return)n;}'
            '(zno)l:=(zzz)(next());(addnew) cached(){(return)wake(l);}')
        body='(?_?)io.read_text("state"){(T_T)(m)=>{} _=>{(o_o)(false);}}'
        body+='(o_o)d.next()==1;(o_o)d.cached()==2;(o_o)d.cached()==2;'
        body+='(o_o)io.input("")==(null);io.write_atomic("state","mine");io.print("isolated");'
        entry=self.source('spec.zzy','(use) "dep.zzy" (as) d;(spec) "a" {'+body+'}(spec) "b" {'+body+'}')
        output=self.output();real=run_bounded;directories=[]
        def mutate(command,**kwargs):
            directories.append(kwargs['cwd'])
            if dependency.exists():dependency.unlink()
            return real(command,**kwargs)
        with patch('zzy.spec_runner.run_bounded',mutate):status=run_specs(entry,output,output.meter.policy,10)
        self.assertEqual(status,0,output.stderr.getvalue())
        self.assertEqual(output.stdout.getvalue().splitlines()[:2],['isolated','isolated'])
        summary=json.loads(output.stdout.getvalue().splitlines()[-1]);self.assertEqual(summary['passed'],2)
        self.assertEqual(len(set(directories)),2);self.assertFalse((self.root/'state').exists())
        self.assertTrue(all(not Path(d).exists() for d in directories))

    def test_spec_dependency_error_location_and_bad_collection(self):
        dependency=self.source('dep.zzy','(addnew) fail(){(return)1/0;}')
        entry=self.source('spec.zzy','(use) "dep.zzy" (as) d;(spec) "a" {d.fail();}')
        result=self.cli('test',entry);self.assertEqual(result[0],1)
        record=json.loads(result[2]);self.assertEqual(Path(record['file']).name,'dep.zzy')
        self.assertEqual(record['span']['start'],{'line':1,'column':26})
        dependency.write_text('broken source',encoding='utf-8')
        entry.write_text('io.write_text("forbidden","x");(use) "dep.zzy" (as) d;(spec) "a" {}',encoding='utf-8')
        result=self.cli('test',entry);self.assertEqual(result[0],1)
        self.assertGreater(json.loads(result[1])['collection_errors'],0)
        self.assertFalse((self.root/'forbidden').exists())

    def test_callback_failure_clears_active_and_runtime_reservations(self):
        for failure in (Cancelled,MemoryError,ResourceExceeded,DiagnosticError):
            program,output=prepared('(zno)a:=[1];(addnew) f(x){io.print(x);(return)x;}array.map(a,f);')
            runtime=Interpreter(program,output);held=[]
            def fail(text):
                held.append(runtime.bindings[id(program.root.children[0])].value)
                self.assertEqual(held[0].active,1)
                if failure is ResourceExceeded:runtime.check('runtime_slots',10**9,program.root)
                if failure is DiagnosticError:runtime.error(program.root,'E201','injected')
                raise failure()
            with patch.object(output,'write',fail):
                with self.assertRaises(failure):runtime.run()
            self.assertEqual(held[0].active,0);self.released(runtime)

    def test_map_freeze_alias_and_nested_machine(self):
        program,output=prepared('(machine) M {a -- "go" --> b;}(zno)m:=data.map();'
            '(zno)a:=[M("a")];data.set(m,"a",a);io.print("probe");')
        runtime=Interpreter(program,output)
        def inspect(text):
            m=runtime.bindings[id(program.root.children[1])].value
            freeze(m,runtime,program.root)
            self.assertTrue(m.frozen);self.assertTrue(m.data['a'].frozen);self.assertTrue(m.data['a'].data[0].frozen)
            with self.assertRaises(DiagnosticError) as caught:m.set(m.keys['a'],m,runtime,program.root)
            self.assertEqual(caught.exception.diagnostic.code,'E203')
            self.assertEqual(list(m.data),['a'])
        with patch.object(output,'write',inspect):runtime.run()
        self.released(runtime)

    def test_sorted_stability_and_map_versions_keep_shared_values(self):
        program,output=prepared('(zno)a:=[2,1,2];(zno)b:=array.sorted(a);'
            '(zno)m:=data.map();data.set(m,"k",a);data.set(m,"k",b);io.print("probe");')
        runtime=Interpreter(program,output)
        def inspect(text):
            a=runtime.bindings[id(program.root.children[0])].value
            b=runtime.bindings[id(program.root.children[1])].value
            m=runtime.bindings[id(program.root.children[2])].value
            self.assertIs(b.data[1],a.data[0]);self.assertIs(b.data[2],a.data[2])
            self.assertIsNot(a,b);self.assertIs(m.data['k'],b)
            self.assertEqual((m.structural_version,m.content_version),(1,2))
        with patch.object(output,'write',inspect):runtime.run()
        self.released(runtime)

    def test_empty_file_and_nul_path_are_regular_results(self):
        file=self.source('empty.zzy','io.print(io.write_atomic("empty",""));io.print(io.read_text("empty"));')
        self.assertEqual(self.cli('run',file),(0,b'(^_^)(null)\n(^_^)()\n',b''))
        self.assertEqual((self.root/'empty').read_bytes(),b'')
        program,output=prepared('io.print(io.read_text('+quote('bad'+chr(0)+'path')+'));')
        Interpreter(program,output).run()
        self.assertTrue(output.stdout.getvalue().startswith('(T_T)(I/O failed:'))

    def test_registry_is_closed_and_query_pure_list_explicit(self):
        self.assertEqual({f.name for f in FUNCTIONS.values() if f.pure},set(PURE_CALLS))
        self.assertEqual(len(FUNCTIONS),sum(len(e.functions) for e in REGISTRY.extensions.values()))
        self.assertEqual({f.name for f in FUNCTIONS.values() if 'callback' in f.effects},{'array.map','array.filter'})
        with self.assertRaises(TypeError):FUNCTIONS['hack']=FUNCTIONS['len']

    def test_json_default_depth_boundaries_and_literal_string_limits(self):
        for depth,status in [(63,0),(64,0),(65,1)]:
            raw='['*depth+'0'+']'*depth
            file=self.source('json.zzy','data.parse('+quote(raw)+');')
            result=self.cli('run',file);self.assertEqual(result[0],status,result[2])
            if status:self.assertIn('value_depth',json.loads(result[2])['message'])


if __name__=='__main__':unittest.main()
