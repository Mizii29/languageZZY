"""Import-safe, closed native ABI used by resolution and execution."""
from types import MappingProxyType
from .metadata import Extension, MetadataRegistry, NativeFunction, NativeType

NAMESPACES = frozenset({'io', 'array', 'text', 'math', 'data', 'unit'})
PURE_CALLS = frozenset({'core.len', 'core.str', 'math.abs', 'text.trim', 'text.contains', 'unit.make', 'unit.format'})
# Parameter names and accepted outer kinds. Empty kind means any ZZY value.
_SPEC = {
 'core.len': ('value', 'Array|String|Map|Range', 'Int'), 'core.str': ('value', 'Int|Float|Bool|Null|String|Quantity', 'String'),
 'core.range': ('start stop step', 'Int Int Int', 'Range'), 'core.wake': ('value', 'Lazy', 'value'),
 'io.print': ('value', '', 'Null'), 'io.input': ('prompt', 'String', 'String|Null'),
 'io.read_text': ('path', 'String', 'Result'),
 'io.write_text': ('path content', 'String String', 'Result'),
 'io.write_atomic': ('path content', 'String String', 'Result'),
 'io.replace_file': ('source target', 'String String', 'Result'),
 'array.copy': ('values', 'Array', 'Array'), 'array.push': ('values value', 'Array *', 'Null'),
 'array.pop': ('values', 'Array', 'value'), 'array.sum': ('values', 'Array', 'Int'),
 'array.stats': ('values', 'Array', 'array.Stats'), 'array.sorted': ('values', 'Array', 'Array'),
 'array.map': ('values callback', 'Array Function', 'Array'),
 'array.filter': ('values callback', 'Array Function', 'Array'),
 'text.trim': ('value', 'String', 'String'), 'text.join': ('values separator', 'Array String', 'String'),
 'text.split': ('value separator', 'String String', 'Array'),
 'text.contains': ('value needle', 'String String', 'Bool'),
 'text.replace': ('old new value', 'String String String', 'String'),
 'text.safe_int': ('value', 'String', 'Result'), 'math.abs': ('value', 'Int|Float', 'value'),
 'data.map': ('', '', 'Map'), 'data.kind': ('value', '', 'String'),
 'data.has': ('map key', 'Map String', 'Bool'), 'data.get': ('map key', 'Map String', 'value'),
 'data.set': ('map key value', 'Map String *', 'Null'), 'data.keys': ('map', 'Map', 'Array'),
 'data.parse': ('text', 'String', 'Result'), 'data.stringify': ('value', '', 'Result'),
 'unit.make': ('value unit_name', 'Int|Float String', 'Quantity'),
 'unit.format': ('quantity unit_name', 'Quantity String', 'String'),
}
_MUTATING = {'array.push','array.pop','data.set'}
_CALLBACKS = {'array.map','array.filter'}
# Direct failures; callback/wake additionally propagate arbitrary user diagnostics.
_ERRORS = {
 'core.range': ('E208',), 'io.print': ('E401',), 'io.input': ('E401',),
 'array.push': ('E203','E206'), 'array.pop': ('E203','E204','E206'),
 'text.split': ('E208',), 'text.replace': ('E208',),
 'data.get': ('E204',), 'data.set': ('E203',),
 'unit.make': ('E306',), 'unit.format': ('E306','E213'),
}
FUNCTIONS = {}
for name, (parameters, types, returns) in _SPEC.items():
 effects = ('io',) if name.startswith('io.') else ('mutation',) if name in _MUTATING else ('callback',) if name in _CALLBACKS else ('lazy',) if name=='core.wake' else ()
 kinds = tuple(() if t=='*' else tuple(t.split('|')) for t in types.split())
 FUNCTIONS[name.removeprefix('core.')] = NativeFunction(name, tuple(parameters.split()), returns,
     effects, ('E201','E202','E211') + _ERRORS.get(name,()), kinds, name in PURE_CALLS,
     name in _CALLBACKS or name=='core.wake')
FUNCTIONS = MappingProxyType(FUNCTIONS)
REGISTRY = MetadataRegistry()
for namespace in (*sorted(NAMESPACES),'core'):
 REGISTRY.register(Extension(namespace,'p05-v1',
     types=(NativeType('array.Stats',True,'context','identity'),) if namespace=='array' else (),
     functions=tuple(f for f in FUNCTIONS.values() if f.name.startswith(namespace+'.'))))
