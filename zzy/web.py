"""Optional ASGI adapter. Importing the core never imports this module."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import io
import json
from pathlib import Path
from threading import Lock, Timer

from .ast_nodes import Node
from .diagnostics import Cancelled, DiagnosticError, Phase, ResourceExceeded
from .interpreter import Interpreter
from .native import json_codec
from .output import Output
from .prepare import prepare
from .resources import CancellationToken, ResourceMeter, ResourcePolicy
from .source import SourceLoader
from .values import CallRequest

MAX_BODY = 65536
MAX_RESPONSE = 65536
MAX_METADATA = 16384
SAFE_INT = 2**53 - 1


class BoundaryError(ValueError):
    pass


def safe_numbers(runtime, value, active=None, depth=0):
    # JSON codec already checks depth/cycles; this walk also precedes serialization.
    runtime.meter.cancellation.check()
    if depth > 64:
        raise BoundaryError("value too deep")
    active = set() if active is None else active
    if value.kind == 'Int' and not -SAFE_INT <= value.data <= SAFE_INT:
        raise BoundaryError('unsafe integer')
    if value.kind in {'Array', 'Map', 'Shape'}:
        if id(value) in active:
            raise BoundaryError('cycle')
        active.add(id(value))
        fields = value.data[1] if value.kind == 'Shape' else value.data
        try:
            for child in fields if value.kind == 'Array' else fields.values():
                safe_numbers(runtime, child, active, depth+1)
        finally:
            active.remove(id(value))


class RequestRuntime(Interpreter):
    def execute_program(self):
        node = self.program.root
        try:
            request = json_codec.parse(self, self.request_text[0], node)
            body = json_codec.parse(self, self.request_text[1], node)
            safe_numbers(self, body)
            request.set(self.scalar("String", "body", node), body, self, node)
        except (json_codec.InvalidJSON, BoundaryError) as error:
            raise BoundaryError('invalid request JSON') from error
        self.input_valid = True
        if getattr(self, "shared_snapshot", None) is None:
            yield from super().execute_program()
        else:
            self.shared_snapshot.attach(self)
        function = self.bindings[id(self.handler)].value
        call = Node('call', self.handler.token, (self.handler, node))
        response = (yield CallRequest(function, [request], call))[0]
        if response.kind not in {'Map', 'Shape'}:
            raise BoundaryError('response must be Map or Shape')
        fields = response.data if response.kind == 'Map' else response.data[1]
        if set(fields) != {'status', 'body'}:
            raise BoundaryError('response fields must be status and body')
        status = fields['status']
        if status.kind != 'Int' or not 200 <= status.data <= 599 or status.data in {204, 205, 304}:
            raise BoundaryError('invalid JSON response status')
        safe_numbers(self, fields['body'])
        payload = json_codec.stringify(self, fields['body'], node).data.encode('utf-8')
        if len(payload) > MAX_RESPONSE:
            raise BoundaryError('response too large')
        self.result = status.data, payload


def create_app(module, routes, *, page=None, timeout=5.0, workers=4, shared=False):
    """Build a fixed GET/POST app. Each handler takes Request Map, returns Response."""
    from starlette.applications import Starlette
    from starlette.responses import Response, JSONResponse
    from starlette.routing import Route
    from starlette.exceptions import HTTPException
    from starlette.requests import ClientDisconnect

    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError('workers must be 1..16')
    if type(timeout) not in (int, float) or not 0 < timeout <= 60:
        raise ValueError('timeout must be 0..60 seconds')
    if type(shared) is not bool:
        raise ValueError('shared must be Bool')
    policy = ResourcePolicy({'io_payload_bytes': MAX_RESPONSE})
    meter = ResourceMeter(policy, Phase.FRONTEND)
    with SourceLoader(meter) as loader:
        program = prepare(loader.read(module), meter, loader)
    functions = {n.token.lexeme: n for n in program.root.children if n.kind == 'function'}
    registry = {}
    for method, path, name in routes:
        if method not in {'GET', 'POST'} or not isinstance(path, str) or not path.startswith('/api/') or any(c in path for c in '{}?#'):
            raise ValueError('routes require GET/POST and literal /api/ paths')
        if (method, path) in registry or name not in functions or len(functions[name].children) != 2:
            raise ValueError('duplicate route or missing one-argument function')
        registry[method, path] = functions[name]
    if not registry:
        raise ValueError('empty routes')
    page_bytes = None
    if page is not None:
        with Path(page).open('rb') as stream:
            page_bytes = stream.read(MAX_RESPONSE + 1)
        if len(page_bytes) > MAX_RESPONSE:
            raise ValueError('page too large')
    pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='zzy-request')
    lock, active = Lock(), set()
    closing = False
    snapshot = None

    def failure(status, code):
        return JSONResponse({'error': {'code': code}}, status_code=status)

    def execute(handler, request_text, token):
        output = Output(io.StringIO(), io.StringIO(), ResourceMeter(policy, Phase.EXECUTION, token))
        runtime = RequestRuntime(program, output, io.StringIO())
        runtime.shared_snapshot = snapshot
        runtime.handler, runtime.request_text, runtime.input_valid = handler, request_text, False
        try:
            runtime.run()
            return runtime.result
        except (json_codec.InvalidJSON, BoundaryError):
            return (500, b'{"error":{"code":"invalid_response"}}') if runtime.input_valid else (400, b'{"error":{"code":"invalid_json"}}')
        except ResourceExceeded:
            return 413 if not runtime.input_valid else 503, b'{"error":{"code":"resource_limit"}}'
        except Cancelled:
            return 504, b'{"error":{"code":"request_timeout"}}'
        except DiagnosticError as error:
            # Preserve source diagnostics in server logs, never expose paths/tracebacks.
            from .diagnostics import render
            import logging
            logging.getLogger('zzy.web').error(render(error.diagnostic).rstrip())
            return 500, b'{"error":{"code":"zzy_error"}}'
        except Exception:
            import logging
            logging.getLogger('zzy.web').exception('internal request failure')
            return 500, b'{"error":{"code":"internal_error"}}'

    @asynccontextmanager
    async def lifespan(app):
        nonlocal closing, snapshot
        try:
            if shared:
                from .web_shared import initialize
                token = CancellationToken()
                timer = Timer(timeout,token.cancel)
                timer.start()
                initializing = pool.submit(initialize,program,policy,token)
                try:
                    snapshot = await asyncio.shield(asyncio.wrap_future(initializing))
                except BaseException:
                    token.cancel()
                    # A cancelled lifespan must still close a late successful snapshot.
                    def discard(future):
                        if not future.cancelled() and future.exception() is None:
                            future.result().close()
                    initializing.add_done_callback(discard)
                    raise
                finally:
                    timer.cancel()
            yield
        finally:
            with lock:
                closing = True
                for token in active:
                    token.cancel()
            await asyncio.to_thread(pool.shutdown, wait=True, cancel_futures=True)
            if snapshot is not None:
                snapshot.close()

    async def endpoint(request):
        key = request.method, request.url.path
        if key not in registry:
            return failure(405, 'method_not_allowed')
        if sum(len(k)+len(v) for k,v in request.scope['headers']) + len(request.scope['query_string']) > MAX_METADATA:
            return failure(431, 'metadata_too_large')
        if request.method == 'POST' and request.headers.get('content-type', '').lower().strip() not in {'application/json', 'application/json; charset=utf-8'}:
            return failure(415, 'unsupported_media_type')
        if request.headers.get('content-encoding', 'identity') != 'identity':
            return failure(415, 'unsupported_encoding')
        token = CancellationToken()
        with lock:
            if closing or len(active) >= workers:
                return failure(503, 'busy')
            active.add(token)
        submitted = False
        try:
            body = bytearray()
            async with asyncio.timeout(timeout):
                async for chunk in request.stream():
                    if len(body)+len(chunk) > MAX_BODY:
                        return failure(413, 'body_too_large')
                    body.extend(chunk)
            if request.method == 'GET' and body:
                return failure(400, 'unexpected_body')
            try:
                raw = body.decode('utf-8') if request.method == 'POST' else 'null'
            except UnicodeError:
                return failure(400, 'invalid_json')
            # Parse body separately so trailing tokens cannot inject Request fields.
            prefix = json.dumps({'method': request.method, 'path': request.url.path,
                                 'query': list(request.query_params.multi_items()),
                                 'headers': list(request.headers.items())}, ensure_ascii=True)
            request_text = (prefix, raw)
            future = pool.submit(execute, registry[key], request_text, token)
            submitted = True
            def finished(_):
                with lock:
                    active.discard(token)
            future.add_done_callback(finished)
            async def disconnected():
                while (await request.receive())['type'] != 'http.disconnect':
                    pass
            watcher = asyncio.create_task(disconnected())
            running = asyncio.wrap_future(future)
            try:
                done, _ = await asyncio.wait({running, watcher}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
                if running in done:
                    status, payload = running.result()
                    return Response(payload, status_code=status, media_type='application/json')
                token.cancel()
                return failure(400, 'disconnected') if watcher in done else failure(504, 'request_timeout')
            finally:
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
        except TimeoutError:
            return failure(408, 'body_timeout')
        except ClientDisconnect:
            token.cancel()
            return failure(400, 'disconnected')
        except asyncio.CancelledError:
            token.cancel()
            raise
        finally:
            if not submitted:
                with lock:
                    active.discard(token)

    async def index(request):
        return Response(page_bytes, media_type='text/html')

    async def http_error(request, error):
        return failure(error.status_code, 'not_found' if error.status_code == 404 else 'method_not_allowed')

    paths = sorted({path for _, path in registry})
    bindings = [Route(path, endpoint, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']) for path in paths]
    if page_bytes is not None:
        bindings.append(Route('/', index, methods=['GET']))
    return Starlette(routes=bindings, lifespan=lifespan, exception_handlers={HTTPException: http_error})


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run an optional ZZY ASGI backend')
    parser.add_argument('module', type=Path)
    parser.add_argument('--route', nargs=3, action='append', required=True, metavar=('METHOD', 'PATH', 'FUNCTION'))
    parser.add_argument('--page', type=Path)
    parser.add_argument('--shared', action='store_true', help='initialize and freeze module state once')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args(argv)
    try:
        import uvicorn
        app = create_app(args.module, args.route, page=args.page, shared=args.shared)
    except ImportError:
        parser.exit(2, 'Web requires the optional install: pip install ".[web]"\n')
    except (ValueError, OSError, DiagnosticError, ResourceExceeded) as error:
        parser.exit(2, str(error) + '\n')
    uvicorn.run(app, host=args.host, port=args.port, timeout_graceful_shutdown=10)


if __name__ == '__main__':
    main()
