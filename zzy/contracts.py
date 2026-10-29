"""Static shape contracts. No interpreter, Web or GUI initialization during generation."""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType

from .diagnostics import Diagnostic, DiagnosticError, Phase, ResourceExceeded, display_path
from .prepare import prepare
from .resources import ResourceMeter, ResourcePolicy
from .source import SourceLoader
from .values import Map, NULL, boolean

SAFE_INT = 2**53 - 1
MAX_SCHEMA = 1024 * 1024
TYPES = {'Int': 'integer', 'Float': 'number', 'String': 'string',
         'Bool': 'boolean', 'Null': 'null', 'Array': 'array', 'Map': 'object'}


class ContractViolation(ValueError):
    def __init__(self, path, reason):
        self.path, self.reason = path, reason
        super().__init__(path + ': ' + reason)


@dataclass(frozen=True)
class Field:
    name: str
    kind: str
    nested: object = None
    default: tuple | None = None


@dataclass(frozen=True)
class Shape:
    name: str
    fields: tuple[Field, ...]
    depth: int


@dataclass(frozen=True)
class RouteContract:
    request: Shape | None
    responses: object


def bound(meter, name, count, limit):
    meter.cancellation.check()
    if count > limit:
        raise ResourceExceeded(name, limit, count, meter.phase, None, None)


def route_registry(program, routes):
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
    return registry


class Compiler:
    def __init__(self, program, meter):
        self.program, self.meter = program, meter
        roots = [program.root, *program.modules.values()]
        self.nodes = {id(n): n for root in roots for n in root.children}
        self.names = {n.token.lexeme: n for n in program.root.children}
        self.active, self.compiled = set(), {}
        self.field_count = 0

    def error(self, node, message):
        raise DiagnosticError(Diagnostic('合约: ' + message, 'E201',
                              display_path(node.token.source.path), node.token.span), Phase.FRONTEND)

    def qualified(self, node, parts):
        for name in parts:
            if node is None or node.kind != 'use':
                return None
            root = self.program.modules[id(node)]
            node = next((n for n in root.children if n.token.lexeme == name and n.kind == 'shape'), None)
        return node

    def named(self, name):
        if type(name) is not str:
            raise ValueError('contract shape name must be String')
        parts = name.split('.')
        node = self.qualified(self.names.get(parts[0]), parts[1:])
        if node is None or node.kind != 'shape':
            raise ValueError('contract requires a statically named shape: ' + name)
        return self.shape(node)

    def literal(self, node):
        while node.kind == 'group':
            node = node.children[0]
        if node.kind == 'unary' and node.token.kind in {'PLUS', 'MINUS'}:
            child = node.children[0]
            while child.kind == 'group':
                child = child.children[0]
            if child.kind in {'integer', 'float'}:
                kind, value = self.literal(child)
                return kind, -value if node.token.kind == 'MINUS' else value
        if node.kind in {'integer', 'float'}:
            return ('Int' if node.kind == 'integer' else 'Float'), self.program.integers[id(node)]
        if node.kind in {'string', 'bool', 'null'}:
            return {'string': 'String', 'bool': 'Bool', 'null': 'Null'}[node.kind], None if node.kind == 'null' else node.data
        self.error(node, '默认值必须为标量常量')

    def shape(self, node):
        key = id(node)
        if key in self.active:
            self.error(node, '不支持递归 shape')
        if key in self.compiled:
            return self.compiled[key]
        bound(self.meter, 'contract_depth', len(self.active)+1, 64)
        self.active.add(key)
        fields = []
        try:
            for field in node.children:
                self.field_count += 1
                bound(self.meter, 'contract_fields', self.field_count, 4096)
                annotation = field.data
                if annotation is None:
                    self.error(field, '字段必须明确注解')
                resolved = self.program.annotations[id(annotation[0] if isinstance(annotation, tuple) else annotation)]
                nested = None
                if isinstance(resolved, tuple):
                    reference, parts = resolved
                    target = self.qualified(self.nodes.get(reference.symbol), parts)
                    if target is None or target.kind != 'shape':
                        self.error(field, '注解必须为静态 shape 或支持的内置类型')
                    nested, kind = self.shape(target), 'Shape'
                else:
                    kind = resolved
                    if kind not in TYPES:
                        self.error(field, '不支持类型 ' + kind)
                default = self.literal(field.children[0]) if field.children else None
                if default is not None:
                    if default[0] != kind:
                        self.error(field, '默认值类型不匹配')
                    if kind == 'Int' and not -SAFE_INT <= default[1] <= SAFE_INT:
                        self.error(field, '默认整数超出 HTTP 安全范围')
                fields.append(Field(field.token.lexeme, kind, nested, default))
            depth = 1 + max((f.nested.depth for f in fields if f.nested), default=0)
            bound(self.meter, 'contract_depth', depth, 64)
            label = node.token.lexeme
            if not label.isascii():
                label = 'U' + label.encode('utf-8').hex()
            result = Shape('S' + str(len(self.compiled)+1) + '_' + label, tuple(fields), depth)
            self.compiled[key] = result
            return result
        finally:
            self.active.remove(key)


def compile_contracts(program, registry, bindings, meter):
    if type(bindings) is not dict:
        raise ValueError('contracts must be an object')
    if any(type(key) is not str for key in bindings):
        raise ValueError('contract route keys must be String')
    bound(meter, 'contract_routes', len(registry), 256)
    bound(meter, 'contract_routes', len(bindings), 256)
    compiler, result = Compiler(program, meter), {}
    for key, binding in sorted(bindings.items()):
        if type(key) is not str or key.count(' ') != 1 or tuple(key.split(' ')) not in registry:
            raise ValueError('contract must reference a registered route')
        method, path = key.split(' ')
        if type(binding) is not dict or not binding or set(binding) - {'request', 'responses'}:
            raise ValueError('contract accepts request/responses only')
        request = None
        if 'request' in binding:
            if method != 'POST':
                raise ValueError('request contract requires POST')
            request = compiler.named(binding['request'])
        responses = binding.get('responses', {})
        if type(responses) is not dict or (request is None and not responses):
            raise ValueError('empty or invalid response contracts')
        if any(type(status) is not str for status in responses):
            raise ValueError('response status keys must be String')
        converted = {}
        for status, shape in sorted(responses.items()):
            if type(status) is not str or len(status) != 3 or not status.isascii() or not status.isdigit() or not 200 <= int(status) <= 599 or int(status) in {204, 205, 304}:
                raise ValueError('response contract requires a JSON response status')
            converted[int(status)] = compiler.named(shape)
        result[method, path] = RouteContract(request, MappingProxyType(converted))
    return MappingProxyType(result)


def field_path(path, key):
    return path + ('.' + key if key.isidentifier() else '[' + json.dumps(key, ensure_ascii=True) + ']')


def convert(runtime, shape, value, node, path='body', depth=1):
    """Check and normalize shape layers only; open containers retain JSON semantics."""
    runtime.meter.cancellation.check()
    bound(runtime.meter, 'contract_path_bytes', len(json.dumps(path, ensure_ascii=True)), 4096)
    runtime.check('value_depth', depth, node)
    if value.kind not in {'Map', 'Shape'}:
        raise ContractViolation(path, 'type')
    source = value.data if value.kind == 'Map' else value.data[1]
    names = {field.name for field in shape.fields}
    for key in source:
        runtime.meter.cancellation.check()
        if key not in names:
            target = field_path(path, key)
            bound(runtime.meter, 'contract_path_bytes', len(json.dumps(target, ensure_ascii=True)), 4096)
            raise ContractViolation(target, 'unknown')
    result = Map(runtime, node)
    for field in shape.fields:
        runtime.meter.cancellation.check()
        target = field_path(path, field.name)
        bound(runtime.meter, 'contract_path_bytes', len(json.dumps(target, ensure_ascii=True)), 4096)
        if field.name in source:
            child = source[field.name]
        elif field.default is None:
            raise ContractViolation(target, 'missing')
        else:
            kind, data = field.default
            child = NULL if kind == 'Null' else boolean(data) if kind == 'Bool' else runtime.scalar(kind, data, node)
        if field.nested is not None:
            child = convert(runtime, field.nested, child, node, target, depth+1)
        elif child.kind != field.kind:
            raise ContractViolation(target, 'type')
        result.set(runtime.scalar('String', field.name, node), child, runtime, node)
    return result


def adapter_schema(status, contract):
    """Adapter failures bypass business contracts, even at a bound status code."""
    codes = {
        400: ['invalid_json', 'unexpected_body', 'disconnected'],
        405: ['method_not_allowed'], 408: ['body_timeout'],
        413: ['body_too_large', 'resource_limit'],
        415: ['unsupported_media_type', 'unsupported_encoding'],
        431: ['metadata_too_large'],
        500: ['invalid_response', 'zzy_error', 'internal_error'],
        503: ['busy', 'resource_limit'], 504: ['request_timeout'],
    }.get(status, [])
    variants = []
    if codes:
        variants.append({'type': 'object', 'properties': {'code': {'enum': codes}},
                         'required': ['code'], 'additionalProperties': False})
    code = ('contract_input' if status == 422 and contract.request else
            'contract_response' if status == 500 and contract.responses else None)
    if code:
        variants.append({'type': 'object', 'properties': {'code': {'const': code},
                         'path': {'type': 'string'}, 'reason': {'enum': ['type', 'missing', 'unknown']}},
                         'required': ['code', 'path', 'reason'], 'additionalProperties': False})
    if not variants:
        return None
    return {'type': 'object', 'properties': {'error': {'anyOf': variants}},
            'required': ['error'], 'additionalProperties': False}


def openapi(registry, contracts, meter):
    schemas = {}
    def reference(shape):
        if shape.name not in schemas:
            properties, required = {}, []
            for field in shape.fields:
                meter.cancellation.check()
                schema = reference(field.nested) if field.nested else {'type': TYPES[field.kind], 'x-zzy-type': field.kind}
                if field.kind == 'Int':
                    schema.update(minimum=-SAFE_INT, maximum=SAFE_INT)
                if field.kind == 'Array':
                    schema['items'] = {}
                if field.kind == 'Map':
                    schema['additionalProperties'] = True
                if field.default is not None:
                    schema['default'] = field.default[1]
                else:
                    required.append(field.name)
                properties[field.name] = schema
            schemas[shape.name] = {'type': 'object', 'properties': properties,
                                  'required': required, 'additionalProperties': False,
                                  'x-zzy-type': 'shape-layout-as-Map'}
        return {'$ref': '#/components/schemas/' + shape.name}
    paths = {}
    for ordinal, ((method, path), handler) in enumerate(sorted(registry.items())):
        contract = contracts.get((method, path))
        operation = {'operationId': method.lower() + '_' + handler.token.lexeme + '_' + str(ordinal),
                     'responses': {'default': {'description': 'Uncontracted business response or adapter error; see x-zzy-rules'}}}
        if contract:
            if contract.request:
                operation['requestBody'] = {'required': True, 'content': {'application/json': {'schema': reference(contract.request)}}}
            for status, shape in contract.responses.items():
                schema = reference(shape)
                adapter = adapter_schema(status, contract)
                if adapter is not None:
                    schema = {'anyOf': [schema, adapter]}
                operation['responses'][str(status)] = {
                    'description': 'Business body contract; adapter errors bypass business validation',
                    'content': {'application/json': {'schema': schema}}}
        paths.setdefault(path, {})[method.lower()] = operation
    document = {'openapi': '3.1.1', 'info': {'title': 'ZZY shape contracts', 'version': '1'},
                'paths': paths, 'components': {'schemas': schemas},
                'x-zzy-rules': {
                    'numeric-tags': 'Int rejects Float including 1.0; Float rejects Int. Bool is distinct. Generic JSON Schema cannot enforce these tags.',
                    'json-boundary': 'Finite Float, safe Int (+/-9007199254740991), Unicode scalar strings, depth/capacity limits also apply inside open Array/Map.',
                    'defaults': 'ZZY fills missing fields on input and contracted output; null is not missing; OpenAPI default is annotation only.',
                    'errors': '422 contract_input before handler; 500 contract_response after handler; error.path and error.reason; adapter errors bypass response contracts.',
                    'business': 'Nonempty and length rules belong to ZZY business logic; unlisted statuses are not shape validated.'}}
    encode_document(document, meter)
    return document


def encode_document(document, meter):
    # Incremental encoding bounds output before accumulating the whole document.
    chunks, size = [], 0
    for chunk in json.JSONEncoder(ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False).iterencode(document):
        size += len(chunk)
        bound(meter, 'contract_document_bytes', size+1, MAX_SCHEMA)
        chunks.append(chunk)
    return (''.join(chunks) + '\n').encode('ascii')


def read_bindings(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate contract configuration key')
            result[key] = value
        return result
    with Path(path).open('rb') as stream:
        data = stream.read(65537)
    if len(data) > 65536:
        raise ValueError('contract configuration exceeds 64 KiB')
    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=pairs)
    except RecursionError:
        raise ValueError('contract configuration too deep') from None


def generate_openapi(module, routes, bindings, *, policy=None):
    meter = ResourceMeter(policy or ResourcePolicy(), Phase.FRONTEND)
    with SourceLoader(meter) as loader:
        program = prepare(loader.read(module), meter, loader)
    registry = route_registry(program, routes)
    contracts = compile_contracts(program, registry, bindings, meter)
    return openapi(registry, contracts, meter)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Export static ZZY shape contracts as OpenAPI 3.1.1')
    parser.add_argument('module', type=Path)
    parser.add_argument('--route', nargs=3, action='append', required=True, metavar=('METHOD', 'PATH', 'FUNCTION'))
    parser.add_argument('--contracts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        document = generate_openapi(args.module, args.route, read_bindings(args.contracts))
        payload = encode_document(document, ResourceMeter(ResourcePolicy(), Phase.FRONTEND))
        if args.output.resolve() in {args.module.resolve(), args.contracts.resolve()} or args.output.suffix.lower() != '.json':
            raise ValueError('output must be a separate .json file')
        args.output.write_bytes(payload)
    except (OSError, ValueError, DiagnosticError, ResourceExceeded) as error:
        parser.exit(2, str(error) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
