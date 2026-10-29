"""Fixed answers, real ZZY execution and static contract rejection; core-only."""
from contextlib import contextmanager
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from zzy.contracts import (ContractViolation, compile_contracts, generate_openapi,
                           openapi, read_bindings, route_registry)
from zzy.diagnostics import Cancelled, DiagnosticError, Phase, ResourceExceeded
from zzy.output import Output
from zzy.prepare import prepare
from zzy.resources import ResourceMeter, ResourcePolicy
from zzy.source import SourceLoader
from zzy.web import RequestRuntime

ROOT = Path(__file__).resolve().parents[1]
ROUTES = [('POST', '/api/test', 'handle')]
BINDINGS = {'POST /api/test': {'request': 'Input', 'responses': {'200': 'Input'}}}
HANDLER = '''(shape) Response {status: (Int); body;}
(addnew) handle(r) {(return) Response::{status:200,body:data.get(r,"body")};}'''


@contextmanager
def compiled(source, bindings=None, policy=None):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'app.zzy'
        path.write_text(source + '\n' + HANDLER, encoding='utf-8')
        meter = ResourceMeter(policy or ResourcePolicy(), Phase.FRONTEND)
        with SourceLoader(meter) as loader:
            program = prepare(loader.read(path), meter, loader)
        registry = route_registry(program, ROUTES)
        table = compile_contracts(program, registry, BINDINGS if bindings is None else bindings, meter)
        yield program, registry, table, meter


def invoke(bundle, payload, policy=None, cancellation=None):
    program, registry, table, _ = bundle
    meter = ResourceMeter(policy or ResourcePolicy(), Phase.EXECUTION, cancellation)
    output = Output(io.StringIO(), io.StringIO(), meter)
    runtime = RequestRuntime(program, output, io.StringIO())
    runtime.handler = registry['POST', '/api/test']
    runtime.request_text = ('{}', json.dumps(payload, ensure_ascii=True))
    runtime.contract = table['POST', '/api/test']
    runtime.input_valid = runtime.validating_response = False
    try:
        runtime.run()
        return json.loads(runtime.result[1])
    finally:
        assert not runtime.bindings
        assert all(meter.used(k) == 0 for k in ('runtime_objects', 'runtime_slots', 'runtime_payload_bytes'))


class ContractTests(unittest.TestCase):
    def test_required_defaults_and_null(self):
        with compiled('(shape) Input {name:(String); n:(Int):=-2; f:(Float):=+1.5; b:(Bool):=(false); nil:(Null):=(null); s:(String):="x";}') as bundle:
            self.assertEqual(invoke(bundle, {'name':'Ada'}), {'name':'Ada','n':-2,'f':1.5,'b':False,'nil':None,'s':'x'})
            for payload, path, reason in [({}, 'body.name', 'missing'), ({'name':None}, 'body.name', 'type'), ({'name':'a','n':None},'body.n','type'), ({'name':'a','extra':1},'body.extra','unknown')]:
                with self.subTest(payload=payload), self.assertRaises(ContractViolation) as caught:
                    invoke(bundle, payload)
                self.assertEqual((caught.exception.path,caught.exception.reason),(path,reason))

    def test_numeric_tags_and_safe_integer(self):
        with compiled('(shape) Input {n:(Int); f:(Float); b:(Bool);}') as bundle:
            for n in [-9007199254740991, 0, 9007199254740991]:
                self.assertEqual(invoke(bundle, {'n':n,'f':1.0,'b':True}), {'n':n,'f':1.0,'b':True})
            for payload in [{'n':True,'f':1.0,'b':True}, {'n':1.0,'f':1.0,'b':True}, {'n':1,'f':1,'b':True}, {'n':1,'f':1.0,'b':1}, {'n':'1','f':1.0,'b':True}]:
                with self.subTest(payload=payload), self.assertRaises(ContractViolation):
                    invoke(bundle, payload)
            from zzy.web import BoundaryError
            for n in [-9007199254740992, 9007199254740992]:
                with self.assertRaises(BoundaryError):
                    invoke(bundle, {'n':n,'f':1.0,'b':True})

    def test_nested_paths_open_containers(self):
        source = '(shape) Task {title:(String);}(shape) Input {task:Task; a:(Array); m:(Map);}'
        with compiled(source) as bundle:
            payload = {'task':{'title':'ok'},'a':[1,'x',True,None,{}],'m':{'untyped':False,'nested':[1.0]}}
            self.assertEqual(invoke(bundle,payload), payload)
            payload['task']['title'] = False
            with self.assertRaises(ContractViolation) as caught: invoke(bundle,payload)
            self.assertEqual(caught.exception.path,'body.task.title')
            payload['task'] = {'title':'ok','a.b':1}
            with self.assertRaises(ContractViolation) as caught: invoke(bundle,payload)
            self.assertEqual(caught.exception.path,'body.task["a.b"]')

    def test_unsupported_definitions_do_not_restrict_plain_shapes(self):
        fields = ['x;', *('x:('+kind+');' for kind in ['Function','Result','Lazy','Range','Machine','Quantity']),
                  'x:sketch.Canvas;', 'x:Input;', 'x:(Array):=[];', 'x:(Map):=data.map();',
                  'x:(Int):=1+2;', 'x:(Int):=len([]);', 'x:(Int):=(true);',
                  'x:(Float):=1;', 'x:(Int):=9007199254740992;']
        for field in fields:
            source = '(shape) Input {'+field+'}'
            with self.subTest(field=field), self.assertRaises(DiagnosticError):
                with compiled(source): pass
            with compiled(source, bindings={}) as bundle:
                self.assertFalse(bundle[2])

    def test_generation_does_not_execute_and_cli_is_core_only(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            marker = folder/'effect.txt'
            source = '(shape) Input {title:(String);}' + HANDLER + '\nio.write_text("'+marker.as_posix()+'","bad"); (zno) later := (zzz)(io.input("bad"));'
            path = folder/'app.zzy'; path.write_text(source,encoding='utf-8')
            config = folder/'routes.json';config.write_text(json.dumps(BINDINGS),encoding='utf-8')
            target = folder/'openapi.json'
            command = [sys.executable,'-X','utf8','-m','zzy.contracts',str(path),'--route',*ROUTES[0],'--contracts',str(config),'--output',str(target)]
            result = subprocess.run(command,cwd=ROOT,capture_output=True,timeout=15)
            self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'',b''))
            self.assertFalse(marker.exists())
            self.assertEqual(json.loads(target.read_bytes()),generate_openapi(path,ROUTES,BINDINGS))
            result = subprocess.run([sys.executable,'-c','import zzy.contracts,zzy.cli,sys;assert not any(x in sys.modules for x in ("starlette","uvicorn","tkinter"))'],capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_input_rejected_before_initialization(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory)/'effect.txt'
            with compiled('(shape) Input {n:(Int);} io.write_text("'+marker.as_posix()+'","executed");') as bundle:
                with self.assertRaises(ContractViolation): invoke(bundle,{'n':False})
                self.assertFalse(marker.exists())
                self.assertEqual(invoke(bundle,{'n':1}),{'n':1})
                self.assertEqual(marker.read_text(),'executed')

    def test_fixed_schema_and_deterministic_generation(self):
        source='(shape) Input {n:(Int); f:(Float); title:(String):="hi"; a:(Array); m:(Map);}'
        with compiled(source) as (program,registry,table,meter):
            document = openapi(registry,table,meter)
            schema = document['components']['schemas']['S1_Input']
            self.assertEqual(schema, {
                'type':'object','properties':{
                    'n':{'type':'integer','x-zzy-type':'Int','minimum':-9007199254740991,'maximum':9007199254740991},
                    'f':{'type':'number','x-zzy-type':'Float'},
                    'title':{'type':'string','x-zzy-type':'String','default':'hi'},
                    'a':{'type':'array','x-zzy-type':'Array','items':{}},
                    'm':{'type':'object','x-zzy-type':'Map','additionalProperties':True}},
                'required':['n','f','a','m'],'additionalProperties':False,'x-zzy-type':'shape-layout-as-Map'})
            self.assertEqual(document,openapi(registry,compile_contracts(program,registry,BINDINGS,meter),meter))
            document['components']['schemas'].clear()
            self.assertTrue(openapi(registry,table,meter)['components']['schemas'])

    def test_imported_shape_static_identity_and_alias_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            (folder/'types.zzy').write_text('(shape) Item {x:(String);}',encoding='utf-8')
            path=folder/'app.zzy'
            path.write_text('(use) "types.zzy" (as) types; (shape) Input {item:types.Item;}'+HANDLER,encoding='utf-8')
            document=generate_openapi(path,ROUTES,BINDINGS)
            self.assertEqual(len(document['components']['schemas']),2)
            direct={'POST /api/test':{'request':'types.Item'}}
            self.assertEqual(len(generate_openapi(path,ROUTES,direct)['components']['schemas']),1)
            path.write_text('(shape) S {x:(Int);} (zno) Alias:=S; (shape) Input {item:Alias;}'+HANDLER,encoding='utf-8')
            with self.assertRaises(DiagnosticError):generate_openapi(path,ROUTES,BINDINGS)

    def test_configuration_rejection(self):
        bad = [[], {'POST /api/missing':{'request':'Input'}}, {'GET /api/test':{'request':'Input'}},
               {'POST /api/test':{}}, {'POST /api/test':{'unknown':1}},
               {'POST /api/test':{'responses':{}}}, {'POST /api/test':{'request':'Missing'}}]
        bad += [{'POST /api/test':{'responses':{status:'Input'}}} for status in ['204','205','304','199','600','default','2XX']]
        for bindings in bad:
            with self.subTest(bindings=bindings),self.assertRaises(ValueError):
                with compiled('(shape) Input {}',bindings):pass
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'config.json'
            for raw in ['{"x":1,"x":2}', ' '*65537, '['*10000]:
                path.write_text(raw,encoding='utf-8')
                with self.assertRaises(ValueError):read_bindings(path)

    def test_conversion_limits_cancellation_and_recovery(self):
        from zzy.resources import CancellationToken
        with compiled('(shape) Input {x:(String):="'+('a'*100)+'";}') as bundle:
            with self.assertRaises(ResourceExceeded):invoke(bundle,{},ResourcePolicy({'runtime_payload_bytes':100}))
            token=CancellationToken();token.cancel()
            with self.assertRaises(Cancelled):invoke(bundle,{},cancellation=token)
            self.assertEqual(invoke(bundle,{}),{'x':'a'*100})
        fields=''.join('a'+str(i)+':(Int);' for i in range(4097))
        with self.assertRaises(ResourceExceeded):
            with compiled('(shape) Input {'+fields+'}'):pass

    def test_one_field_change_updates_validation_and_schema(self):
        for annotation, value, wrong, schema_type in [('String','x',1,'string'),('Int',1,'x','integer')]:
            with compiled('(shape) Input {x:('+annotation+');}') as bundle:
                self.assertEqual(invoke(bundle,{'x':value}),{'x':value})
                with self.assertRaises(ContractViolation):invoke(bundle,{'x':wrong})
                schema=openapi(bundle[1],bundle[2],bundle[3])['components']['schemas']['S1_Input']
                self.assertEqual(schema['properties']['x']['type'],schema_type)

    def test_response_defaults_and_distinct_operation_ids(self):
        with compiled('(shape) Input {x:(Int):=5;}',{'POST /api/test':{'responses':{'200':'Input'}}}) as bundle:
            self.assertEqual(invoke(bundle,{}),{'x':5})
            registry={('GET','/api/a'):bundle[1]['POST','/api/test'],('GET','/api/b'):bundle[1]['POST','/api/test'],
                      ('POST','/api/a'):bundle[1]['POST','/api/test'],('POST','/api/b'):bundle[1]['POST','/api/test']}
            document=openapi(registry,{},bundle[3])
            ids=[op['operationId'] for path in document['paths'].values() for op in path.values()]
            self.assertEqual(len(ids),len(set(ids)))

    def test_unicode_names_and_bounded_diagnostics(self):
        with compiled('(shape) 任务 {标题:(String);}(shape) Input {任务:任务;}') as bundle:
            self.assertEqual(invoke(bundle,{'任务':{'标题':'测试'}}),{'任务':{'标题':'测试'}})
            document=openapi(bundle[1],bundle[2],bundle[3])
            for name in document['components']['schemas']:
                self.assertRegex(name,r'^[a-zA-Z0-9._-]+$')
            with self.assertRaises(ResourceExceeded):invoke(bundle,{'中'*1000:1})

    def test_depth_bound_and_failed_cli_does_not_overwrite(self):
        prefix='(shape) S0 {x:(Int);}'
        for i in range(1,65):prefix+='(shape) S'+str(i)+' {x:S'+str(i-1)+';}'
        with self.assertRaises(ResourceExceeded):
            with compiled(prefix+'(shape) Input {x:S64;}'):pass
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);path=folder/'app.zzy';config=folder/'routes.json';output=folder/'out.json'
            path.write_text('(shape) Input {x:(Int):=len([]);}'+HANDLER,encoding='utf-8')
            config.write_text(json.dumps(BINDINGS),encoding='utf-8');output.write_text('keep',encoding='utf-8')
            args=[sys.executable,'-X','utf8','-m','zzy.contracts',str(path),'--route',*ROUTES[0],'--contracts',str(config),'--output',str(output)]
            result=subprocess.run(args,capture_output=True,timeout=15)
            self.assertEqual(result.returncode,2);self.assertNotIn(b'Traceback',result.stderr)
            self.assertEqual(output.read_text(),'keep')


if __name__ == '__main__':unittest.main()
