"""Explicit optional suite: real TCP HTTP, no skipped tests or mock transport."""
import argparse
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

    def test_invalid_routes_rejected_before_serving(self):
        for routes in [[],[('GET','/api/{name}','hello')],[('GET','/api/a','missing')],[('GET','/api/a','hello')]*2]:
            with self.assertRaises(ValueError):create_app(ROOT/'examples/web/app.zzy',routes)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(HTTPTests)
    passed,report=execute(suite)
    report['dependencies']={x:importlib.metadata.version(x) for x in ('starlette','uvicorn','anyio','h11')}
    if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report));return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
