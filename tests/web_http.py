"""Explicit optional suite: real TCP HTTP, no skipped tests or mock transport."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import http.client
import importlib.metadata
import json
from pathlib import Path
import socket
import threading
import time
import unittest
import uvicorn
from zzy.web import create_app
from tests.__main__ import execute

ROOT=Path(__file__).resolve().parents[1]

@contextmanager
def server(module, routes, **kwargs):
    app=create_app(ROOT/module,routes,**kwargs)
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    instance=uvicorn.Server(uvicorn.Config(app,log_level='critical',lifespan='on'))
    thread=threading.Thread(target=instance.run,kwargs={'sockets':[sock]})
    thread.start()
    try:
        deadline=time.monotonic()+10
        while not instance.started:
            if not thread.is_alive() or time.monotonic()>deadline:raise AssertionError('server startup failed')
            time.sleep(.01)
        yield port
    finally:
        instance.should_exit=True;thread.join(10);sock.close()
        if thread.is_alive():raise AssertionError('server failed to shut down')


def request(port,path='/api/hello',method='GET',body=None,headers=None):
    connection=http.client.HTTPConnection('127.0.0.1',port,timeout=10)
    try:
        connection.request(method,path,body=body,headers=headers or {})
        response=connection.getresponse()
        return response.status,response.getheader('content-type'),response.read()
    finally:connection.close()


class HTTPTests(unittest.TestCase):
    def test_contract_example_default_shared_and_openapi(self):
        from zzy.contracts import generate_openapi, read_bindings
        routes=[('POST','/api/tasks','submit')]
        bindings=read_bindings(ROOT/'examples/contracts/routes.json')
        expected=generate_openapi(ROOT/'examples/contracts/app.zzy',routes,bindings)
        for shared in (False,True):
            with self.subTest(shared=shared),server('examples/contracts/app.zzy',routes,contracts=bindings,shared=shared) as port:
                status,_,data=request(port,'/openapi.json')
                self.assertEqual(status,200);self.assertEqual(json.loads(data),expected)
                cases=[({'task':{'title':'  homework  '}},200,{'title':'homework','priority':1,'accepted':True}),
                       ({'task':{'title':False}},422,{'error':{'code':'contract_input','path':'body.task.title','reason':'type'}}),
                       ({'task':{'title':' '}},409,{'message':'标题长度必须为1至80'}),
                       ({'task':{'title':'ok','priority':6}},409,{'message':'优先级必须为1至5'})]
                for payload,status,expected_body in cases:
                    actual,_,data=request(port,'/api/tasks','POST',json.dumps(payload).encode(),{'Content-Type':'application/json'})
                    self.assertEqual((actual,json.loads(data)),(status,expected_body))

    def test_contract_rejection_before_business_and_response_statuses(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);path=folder/'app.zzy';marker=folder/'called.txt'
            path.write_text('''(shape) Input {n:(Int);}
(shape) Good {answer:(Int);}
(shape) Response {status:(Int);body;}
(addnew) handle(r) {
io.write_text("MARKER","called");
(zno) n:=data.get(data.get(r,"body"),"n");
(zif?:) n==0 {(return) Response::{status:409,body:"business failure"};}
(zif?:) n==1 {(return) Response::{status:200,body:data.map()};}
(return) Response::{status:200,body:Good::{answer:n}};
}'''.replace('MARKER',marker.as_posix()),encoding='utf-8')
            routes=[('POST','/api/test','handle'),('POST','/api/plain','handle')]
            bindings={'POST /api/test':{'request':'Input','responses':{'200':'Good','422':'Good','500':'Good'}}}
            with server(path,routes,contracts=bindings) as port:
                def post(path,payload):
                    status,_,data=request(port,path,'POST',json.dumps(payload).encode(),{'Content-Type':'application/json'})
                    self.assertNotIn(b'Traceback',data)
                    return status,json.loads(data)
                self.assertEqual(post('/api/test',{})[0],422);self.assertFalse(marker.exists())
                self.assertEqual(post('/api/test',{'n':0}),(409,'business failure'))
                self.assertEqual(post('/api/test',{'n':1}),(500,{'error':{'code':'contract_response','path':'body.answer','reason':'missing'}}))
                self.assertEqual(post('/api/plain',{'n':1}),(200,{}))
                self.assertEqual(post('/api/test',{'n':2}),(200,{'answer':2}))

    def test_contract_interleaving_isolation_and_resource_recovery(self):
        from unittest.mock import patch
        from zzy.web import RequestRuntime
        from zzy.contracts import read_bindings
        barrier=threading.Barrier(2)
        original=RequestRuntime.execute_program
        def interleaved(runtime):
            barrier.wait(timeout=5)
            yield from original(runtime)
        bindings=read_bindings(ROOT/'examples/contracts/routes.json')
        for shared in (False,True):
            with server('examples/contracts/app.zzy',[('POST','/api/tasks','submit')],contracts=bindings,shared=shared) as port:
                with patch.object(RequestRuntime,'execute_program',interleaved),ThreadPoolExecutor(2) as pool:
                    def call(i):
                        return request(port,'/api/tasks','POST',json.dumps({'task':{'title':str(i)}}).encode(),{'Content-Type':'application/json'})
                    results=list(pool.map(call,range(8)))
                self.assertEqual([json.loads(r[2]) for r in results],[{'title':str(i),'priority':1,'accepted':True} for i in range(8)])
                # A huge reflected unknown key must not produce an unbounded error response.
                status,_,data=request(port,'/api/tasks','POST',json.dumps({'x'*5000:1}).encode(),{'Content-Type':'application/json'})
                self.assertEqual((status,json.loads(data)),(503,{'error':{'code':'resource_limit'}}))
                status,_,_=request(port,'/api/tasks','POST',b'{"task":{"title":"after"}}',{'Content-Type':'application/json'})
                self.assertEqual(status,200)

    def test_contract_generation_rejects_bad_shapes_before_shared_init(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);marker=folder/'effect';path=folder/'app.zzy'
            path.write_text('io.write_text("'+marker.as_posix()+'","bad");(shape) Input {x:(Int):=len([]);}(addnew) handle(r){(return)r;}',encoding='utf-8')
            from zzy.diagnostics import DiagnosticError
            with self.assertRaises(DiagnosticError):
                create_app(path,[('POST','/api/test','handle')],contracts={'POST /api/test':{'request':'Input'}},shared=True)
            self.assertFalse(marker.exists())

    def test_contract_open_container_mutation_is_per_request(self):
        import tempfile
        from unittest.mock import patch
        from zzy.web import RequestRuntime
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'app.zzy'
            path.write_text('''(shape) Input {n:(Int); a:(Array); m:(Map);}
(shape) Response {status:(Int);body;}
(addnew) handle(r) {
(zno) body:=data.get(r,"body");
array.push(data.get(body,"a"),data.get(body,"n"));
data.set(data.get(body,"m"),"id",data.get(body,"n"));
(return) Response::{status:200,body:body};}''',encoding='utf-8')
            bindings={'POST /api/test':{'request':'Input','responses':{'200':'Input'}}}
            barrier=threading.Barrier(2);original=RequestRuntime.execute_program
            def interleaved(runtime):
                barrier.wait(timeout=5)
                yield from original(runtime)
            for shared in (False,True):
                with server(path,[('POST','/api/test','handle')],contracts=bindings,shared=shared) as port:
                    with patch.object(RequestRuntime,'execute_program',interleaved),ThreadPoolExecutor(2) as pool:
                        def call(i):
                            status,_,body=request(port,'/api/test','POST',json.dumps({'n':i,'a':[1],'m':{}}).encode(),{'Content-Type':'application/json'})
                            self.assertEqual(status,200)
                            return json.loads(body)
                        results=list(pool.map(call,range(8)))
                    self.assertEqual(results,[{'n':i,'a':[1,i],'m':{'id':i}} for i in range(8)])

    def test_sqlite_http_restart_and_validation(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'app.zzy';database=Path(directory)/'tasks.sqlite3'
            path.write_text((ROOT/'examples/sqlite/app.zzy').read_text(encoding='utf-8').replace('examples/sqlite/tasks.sqlite3',database.as_posix()),encoding='utf-8')
            routes=[('GET','/api/tasks','handle'),('POST','/api/tasks','handle')]
            with server(path,routes,shared=True) as port:
                self.assertEqual(request(port,'/api/tasks','POST',b'{}',{'Content-Type':'application/json'})[0],422)
                status,_,body=request(port,'/api/tasks','POST',b'{"title":"homework"}',{'Content-Type':'application/json'})
                self.assertEqual(status,200);self.assertEqual(json.loads(body),[[1,'homework']])
            with server(path,routes,shared=True) as port:
                status,_,body=request(port,'/api/tasks')
                self.assertEqual(status,200);self.assertEqual(json.loads(body),[[1,'homework']])

    def test_python_embedding_matches_http_business_function(self):
        from zzy.embedding import load_module
        with load_module(ROOT/'examples/web/app.zzy') as module:
            with server('examples/web/app.zzy',[('POST','/api/greet','greet')],shared=True) as port:
                for body in [{'name':'Ada'}, {'name':'同学'}, {}, {'name':True}, None]:
                    expected=module.call('greet',{'body':body}).value
                    status,_,payload=request(port,'/api/greet','POST',json.dumps(body).encode(),{'Content-Type':'application/json'})
                    self.assertEqual(status,expected['status'])
                    self.assertEqual(json.loads(payload),expected['body'])

    def test_page_get_post_and_business_errors(self):
        with server('examples/web/app.zzy',[('GET','/api/hello','hello'),('POST','/api/greet','greet')],page=ROOT/'examples/web/index.html') as port:
            status,ctype,body=request(port)
            self.assertEqual(status,200);self.assertEqual(json.loads(body)['language'],'ZZY')
            self.assertIn('application/json',ctype)
            status,ctype,body=request(port,'/')
            self.assertEqual(status,200);self.assertIn('text/html',ctype);self.assertIn(b"fetch(path,options)",body)
            for payload,status in [(b'{"name":"Ada"}',200),(b'{}',422),(b'{"name":true}',422),(b'null',422)]:
                self.assertEqual(request(port,'/api/greet','POST',payload,{'Content-Type':'application/json'})[0],status)
            self.assertEqual(request(port,'/unknown')[0],404)
            self.assertEqual(request(port,'/api/hello','POST')[0],405)
            self.assertEqual(request(port,'/api/greet','POST',b'{}')[0],415)

    def test_strict_json_and_recovery(self):
        with server('tests/p08/edge.zzy',[('POST','/api/echo','echo')]) as port:
            for body in [b'{"a":1,"a":2}',b'NaN',b'1e400',b'9007199254740992',b'"\\ud800"',b'1,"extra":2',b'\xff',b'']:
                with self.subTest(body=body):
                    status,_,data=request(port,'/api/echo','POST',body,{'Content-Type':'application/json'})
                    self.assertEqual(status,400);self.assertEqual(json.loads(data)['error']['code'],'invalid_json')
            for body in [b'true',b'1',b'null',b'9007199254740991',b'"9007199254740992"']:
                status,_,data=request(port,'/api/echo','POST',body,{'Content-Type':'application/json'})
                self.assertEqual(status,200);self.assertEqual(json.loads(data),[json.loads(body),1])

    def test_size_and_output_failures(self):
        routes=[('POST','/api/echo','echo')]+[('GET','/api/'+x,x) for x in ('big','result','badstatus','boom')]
        with server('tests/p08/edge.zzy',routes) as port:
            for n,status in [(65536,200),(65537,413)]:
                body=b'0'+b' '*(n-1)
                self.assertEqual(request(port,'/api/echo','POST',body,{'Content-Type':'application/json'})[0],status)
            for x in ('big','result','badstatus','boom'):
                status,_,body=request(port,'/api/'+x)
                self.assertEqual(status,500);self.assertNotIn(b'Traceback',body);self.assertNotIn(b'.zzy',body)
            self.assertEqual(request(port,'/api/echo','POST',b'{}',{'Content-Type':'application/json'})[0],200)

    def test_timeout_and_next_request(self):
        with server('tests/p08/edge.zzy',[('GET','/api/loop','loop'),('POST','/api/echo','echo')],timeout=.2) as port:
            self.assertEqual(request(port,'/api/loop')[0],504)
            self.assertEqual(request(port,'/api/echo','POST',b'42',{'Content-Type':'application/json'})[0],200)

    def test_concurrent_requests_do_not_share_module_binding(self):
        with server('tests/p08/edge.zzy',[('POST','/api/echo','echo')]) as port:
            with ThreadPoolExecutor(2) as pool:
                replies=list(pool.map(lambda i:request(port,'/api/echo','POST',str(i).encode(),{'Content-Type':'application/json'}),range(12)))
            for i,(status,_,body) in enumerate(replies):
                self.assertEqual(status,200);self.assertEqual(json.loads(body),[i,1])

    def test_disconnect_releases_worker_and_shutdown_cancels(self):
        with server('tests/p08/edge.zzy',[('GET','/api/loop','loop'),('POST','/api/echo','echo')],workers=1,timeout=2) as port:
            sock=socket.create_connection(('127.0.0.1',port))
            sock.sendall(b'GET /api/loop HTTP/1.1\r\nHost: localhost\r\n\r\n')
            time.sleep(.05);sock.close()
            deadline=time.monotonic()+1
            while True:
                status,_,body=request(port,'/api/echo','POST',b'1',{'Content-Type':'application/json'})
                if status==200:break
                self.assertEqual(status,503)
                if time.monotonic()>deadline:self.fail('disconnect did not free worker')
                time.sleep(.01)
            self.assertEqual(json.loads(body),[1,1])

    def test_slow_body_timeout_and_metadata_bound(self):
        with server('tests/p08/edge.zzy',[('POST','/api/echo','echo')],timeout=.15) as port:
            c=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
            c.putrequest('POST','/api/echo');c.putheader('Content-Type','application/json');c.putheader('Content-Length','4');c.endheaders();c.send(b'{')
            self.assertEqual(c.getresponse().status,408);c.close()
            self.assertEqual(request(port,'/api/echo','POST',b'0',{'Content-Type':'application/json','X-Pad':'x'*16400})[0],431)

    def test_shared_interleaved_requests_and_write_recovery(self):
        from unittest.mock import patch
        from zzy.web import RequestRuntime
        barrier=threading.Barrier(2)
        original=RequestRuntime.execute_program
        def interleaved(runtime):
            if runtime.handler.token.lexeme=='local_state':barrier.wait(timeout=5)
            yield from original(runtime)
        routes=[('GET','/api/'+n,n) for n in ('read','array_write','map_write','shape_write','machine_write','default_write')]
        routes.append(('POST','/api/local','local_state'))
        with server('tests/p08/shared.zzy',routes,shared=True) as port:
            with patch.object(RequestRuntime,'execute_program',interleaved),ThreadPoolExecutor(2) as pool:
                replies=list(pool.map(lambda i:request(port,'/api/local','POST',str(i).encode(),{'Content-Type':'application/json'}),range(8)))
            for i,(status,_,body) in enumerate(replies):
                self.assertEqual(status,200);self.assertEqual(json.loads(body),[None,i])
            for name in ('array_write','map_write','shape_write','machine_write','default_write'):
                self.assertEqual(request(port,'/api/'+name)[0],500)
                self.assertEqual(json.loads(request(port,'/api/read')[2]),[[1,2],[7],'a'])

    def test_cancelled_startup_closes_late_snapshot(self):
        from unittest.mock import patch
        from zzy import web_shared
        entered,release=threading.Event(),threading.Event()
        snapshots=[];original=web_shared.initialize
        def paused(*args):
            snapshot=original(*args);snapshots.append(snapshot);entered.set()
            if not release.wait(5):raise AssertionError('test barrier timed out')
            return snapshot
        async def scenario():
            app=create_app(ROOT/'tests/p08/shared.zzy',[('GET','/api/read','read')],shared=True)
            context=app.router.lifespan_context(app)
            task=asyncio.create_task(context.__aenter__())
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait,5))
                task.cancel()
                await asyncio.sleep(0)
            finally:release.set()
            with self.assertRaises(asyncio.CancelledError):await task
        with patch.object(web_shared,'initialize',paused):asyncio.run(scenario())
        self.assertEqual(len(snapshots),1)
        self.assertTrue(snapshots[0].closed)
        self.assertTrue(all(snapshots[0].meter.used(k)==0 for k in ('runtime_objects','runtime_slots','runtime_payload_bytes')))

    def test_shared_lifespan_releases_service_owned_reservations(self):
        from unittest.mock import patch
        from zzy import web_shared
        snapshots=[]
        original=web_shared.initialize
        def observed(*args):
            snapshot=original(*args);snapshots.append(snapshot);return snapshot
        with patch.object(web_shared,'initialize',observed):
            with server('tests/p08/shared.zzy',[('GET','/api/read','read')],shared=True) as port:
                self.assertEqual(request(port,'/api/read')[0],200)
                self.assertEqual(request(port,'/api/read')[0],200)
                self.assertEqual(len(snapshots),1)
                self.assertFalse(snapshots[0].closed)
                self.assertGreater(snapshots[0].meter.used('runtime_slots'),0)
        self.assertTrue(snapshots[0].closed)
        self.assertTrue(all(snapshots[0].meter.used(k)==0 for k in ('runtime_objects','runtime_slots','runtime_payload_bytes')))

    def test_event_loop_responds_during_busy_worker(self):
        with server('tests/p08/shared.zzy',[('GET','/api/loop','loop')],workers=1,timeout=.6,shared=True) as port:
            with ThreadPoolExecutor(1) as pool:
                running=pool.submit(request,port,'/api/loop')
                time.sleep(.1)
                started=time.monotonic()
                self.assertEqual(request(port,'/api/loop')[0],503)
                self.assertLess(time.monotonic()-started,.4)
                self.assertEqual(running.result()[0],504)

    def test_invalid_routes_rejected_before_serving(self):
        for routes in [[],[('GET','/api/{name}','hello')],[('GET','/api/a','missing')],[('GET','/api/a','hello')]*2]:
            with self.assertRaises(ValueError):create_app(ROOT/'examples/web/app.zzy',routes)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    from tests.schema_contracts import SchemaTests
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in (HTTPTests,SchemaTests)])
    passed,report=execute(suite)
    report['dependencies']={x:importlib.metadata.version(x) for x in ('starlette','uvicorn','anyio','h11','jsonschema','attrs','referencing','rpds-py','jsonschema-specifications')}
    if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report));return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
