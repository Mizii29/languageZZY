"""Public, core-only Python embedding with one owned context per call."""
from dataclasses import dataclass
import io
import math
from threading import Lock

from .ast_nodes import Node
from .diagnostics import Diagnostic, DiagnosticError, Phase
from .interpreter import Interpreter
from .native.json_codec import InvalidJSON, utf8_size
from .output import Output
from .prepare import prepare
from .resources import CancellationToken, ResourceMeter, ResourcePolicy
from .source import SourceLoader
from .values import Array, CallRequest, Map, NULL, boolean

__all__ = ['load_module', 'LoadedModule', 'CallResult', 'ConversionError']


class ConversionError(ValueError):
    """The boundary rejects unsupported data; it never executes conversion hooks."""


@dataclass(frozen=True)
class CallResult:
    value: object
    stdout: str
    stderr: str


class _Converter:
    def __init__(self, runtime, node):
        self.r, self.node = runtime, node

    def string(self, text):
        self.r.check('text_codepoints', len(text), self.node)
        try:
            return utf8_size(self.r, text, self.node)
        except InvalidJSON as error:
            raise ConversionError(str(error)) from None

    def container(self, item, length, active, depth):
        self.r.check('value_depth', depth + 1, self.node)
        self.r.check('container_items', length, self.node)
        if id(item) in active:
            raise ConversionError('cyclic data is not supported')
        active.add(id(item))

    def from_python(self, item, active=None, depth=0):
        self.r.meter.cancellation.check()
        kind = type(item)
        if item is None:
            return NULL
        if kind is bool:
            return boolean(item)
        if kind is int:
            return self.r.scalar('Int', item, self.node)
        if kind is float:
            if not math.isfinite(item):
                raise ConversionError('Float must be finite')
            return self.r.scalar('Float', item, self.node)
        if kind is str:
            self.string(item)
            return self.r.scalar('String', item, self.node)
        if kind not in (list, dict):
            raise ConversionError('expected exact None/bool/int/float/str/list/dict')
        active = set() if active is None else active
        self.container(item, len(item), active, depth)
        try:
            result = Array(self.r, self.node) if kind is list else Map(self.r, self.node)
            if kind is list:
                for child in item:
                    result.push(self.from_python(child, active, depth+1), self.r, self.node)
            else:
                for key, child in item.items():
                    if type(key) is not str:
                        raise ConversionError('Map keys must be exact str')
                    value_key = self.from_python(key)
                    result.set(value_key, self.from_python(child, active, depth+1), self.r, self.node)
            return result
        finally:
            active.remove(id(item))

    def retain(self, **amounts):
        # Python output storage remains accounted until the call has completed.
        self.r.slots.append(self.r.reserve(self.node, **amounts))

    def to_python(self, item, active=None, depth=0):
        self.r.meter.cancellation.check()
        kind, data = item.kind, item.data
        if getattr(item, 'native_type', None) is not None:
            raise ConversionError('native handles cannot cross the boundary')
        if kind in {'Null', 'Bool'}:
            return data
        if kind == 'Int':
            self.r.check('integer_bits', data.bit_length(), self.node)
            self.retain(runtime_payload_bytes=(data.bit_length()+7)//8)
            return data
        if kind == 'Float':
            if not math.isfinite(data):
                raise ConversionError('Float must be finite')
            self.retain(runtime_payload_bytes=8)
            return data
        if kind == 'String':
            self.string(data)
            self.retain(runtime_payload_bytes=4*len(data))
            return data
        if kind not in {'Array', 'Map', 'Shape'}:
            raise ConversionError(kind + ' cannot cross the boundary')
        fields = data[1] if kind == 'Shape' else data
        active = set() if active is None else active
        self.container(item, len(fields), active, depth)
        try:
            self.retain(runtime_objects=1, runtime_slots=len(fields)*(1 if kind == 'Array' else 2))
            if kind == 'Array':
                return [self.to_python(child, active, depth+1) for child in fields]
            result = {}
            for key, child in fields.items():
                self.string(key)
                self.retain(runtime_payload_bytes=4*len(key))
                result[key] = self.to_python(child, active, depth+1)
            return result
        finally:
            active.remove(id(item))


class _CallRuntime(Interpreter):
    def execute_program(self):
        converter = _Converter(self, self.handler)
        self.check('io_payload_bytes', converter.string(self.input_text), self.handler)
        self.slots.append(self.reserve(self.handler, runtime_payload_bytes=4*len(self.input_text),
                                       runtime_slots=len(self.arguments)))
        self.stdin = io.StringIO(self.input_text)
        arguments = [converter.from_python(arg) for arg in self.arguments]
        yield from super().execute_program()
        function = self.bindings[id(self.handler)].value
        call = Node('call', self.handler.token, (self.handler,)*(len(arguments)+1))
        value = (yield CallRequest(function, arguments, call))[0]
        self.result = converter.to_python(value)


class LoadedModule:
    """Prepared source snapshot. Use load_module() and close()/with to own it."""
    def __init__(self, program, policy):
        self._program, self._policy = program, policy
        self._functions = {n.token.lexeme: n for n in program.root.children if n.kind == 'function'}
        self._lock = Lock()
        self._active = 0
        self._closed = False

    def _ensure_open(self):
        if self._closed:
            raise RuntimeError('module is closed')

    @property
    def exports(self):
        with self._lock:
            self._ensure_open()
            return tuple(self._functions)

    def call(self, name, *arguments, stdin='', cancellation=None):
        if type(name) is not str or type(stdin) is not str:
            raise TypeError('name and stdin must be exact str')
        if cancellation is not None and type(cancellation) is not CancellationToken:
            raise TypeError('cancellation must be CancellationToken or None')
        with self._lock:
            self._ensure_open()
            if name not in self._functions:
                raise LookupError('unknown exported function: ' + name)
            handler = self._functions[name]
            if len(arguments) != len(handler.children)-1:
                raise TypeError('incorrect argument count for ' + name)
            program = self._program
            self._active += 1
        try:
            stdout, stderr = io.StringIO(), io.StringIO()
            output = Output(stdout, stderr, ResourceMeter(self._policy, Phase.EXECUTION, cancellation))
            runtime = _CallRuntime(program, output, io.StringIO())
            runtime.handler, runtime.arguments, runtime.input_text = handler, arguments, stdin
            try:
                runtime.run()
                return CallResult(runtime.result, stdout.getvalue(), stderr.getvalue())
            except (MemoryError, RecursionError) as error:
                raise DiagnosticError(Diagnostic('宿主资源不足：'+type(error).__name__, 'E211'),
                                      Phase.EXECUTION) from None
            finally:
                runtime.arguments = ()
                runtime.input_text = ''
                runtime.stdin.close()
                stdout.close()
                stderr.close()
        finally:
            with self._lock:
                self._active -= 1

    def close(self):
        with self._lock:
            if self._active:
                raise RuntimeError('calls are active; cancel and join them before close')
            self._closed = True
            self._program = None
            self._functions.clear()

    def __enter__(self):
        with self._lock:
            self._ensure_open()
        return self

    def __exit__(self, *exception):
        self.close()


def load_module(path, *, policy=None):
    """Prepare a source/dependency snapshot without running user code."""
    if policy is not None and type(policy) is not ResourcePolicy:
        raise TypeError('policy must be ResourcePolicy or None')
    policy = ResourcePolicy() if policy is None else policy
    meter = ResourceMeter(policy, Phase.FRONTEND)
    with SourceLoader(meter) as loader:
        program = prepare(loader.read(path), meter, loader)
    return LoadedModule(program, policy)
