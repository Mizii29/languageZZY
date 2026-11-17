"""Development-only inventory. Never imported or invoked by the native executable."""
import argparse
import ast
from dataclasses import asdict, fields
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def snapshot():
    from zzy.ast_nodes import Program, Reference, Symbol, Capture, FunctionPlan
    from zzy.native.catalog import FUNCTIONS, REGISTRY, PURE_CALLS
    from zzy.resources import ResourcePolicy
    from zzy.tokens import FIXED_TOKENS, RESERVED_NAMES
    from zzy.resolver import BUILTIN_NAMES, IMPLEMENTED_NAMES
    from tests.blackbox import DEFAULT_MANIFESTS, load_cases

    def calls(path, name, index=0):
        def choices(value):
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return [value.value]
            if isinstance(value, ast.IfExp):
                return choices(value.body) + choices(value.orelse)
            return []
        tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
        return sorted({value for node in ast.walk(tree)
            if isinstance(node, ast.Call) and len(node.args) > index
            and ((isinstance(node.func, ast.Name) and node.func.id == name)
                 or (isinstance(node.func, ast.Attribute) and node.func.attr == name))
            for value in choices(node.args[index])})

    paths = sorted({*('zzy/' + p for p in ('ast_nodes.py', 'parser.py', 'resolver.py',
        'values.py', 'interpreter.py', 'resources.py', 'diagnostics.py', 'tokens.py')),
        'zzy/native/catalog.py', 'zzy/native/sketch_metadata.py',
        *(p.relative_to(ROOT).as_posix() for p in DEFAULT_MANIFESTS)})
    # Only imports descriptor modules: no user module initialization, Tk or ASGI.
    assert not any(n in sys.modules for n in ('tkinter', 'starlette', 'uvicorn'))
    return dict(schema_version=1,
        source_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
        source_hashes={p: hashlib.sha256((ROOT / p).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in paths},
        fixed_tokens=dict(sorted(FIXED_TOKENS.items())), reserved_names=sorted(RESERVED_NAMES),
        ast_kinds=sorted(set(calls('zzy/parser.py', 'node')) | {
            'keep', 'order', 'take', 'yield', 'assert', 'trace', 'break', 'continue',
            'integer', 'float', 'name', 'bool', 'null'}),
        dynamic_ast_sources=['kind.lower(): query clause', 'token.kind.lower(): assert/trace/break/continue',
                             'primary kind mapping: integer/float/name/bool/null'],
        value_constructors={p.relative_to(ROOT).as_posix(): calls(p.relative_to(ROOT), 'Value')
            for p in sorted((ROOT / 'zzy').rglob('*.py')) if calls(p.relative_to(ROOT), 'Value')},
        value_kinds=['Null','Bool','Int','Float','String','Array','Map','Shape','Function','Result',
            'Lazy','Machine','Quantity','Range','Module','Namespace','Definition','MachineDefinition',
            'NativeType','sketch.Canvas','sketch.Pen','sketch.Layer','sketch.Color','sketch.Drawing'],
        value_subclasses=calls('zzy/values.py', '__init__'),
        reference_kinds=calls('zzy/resolver.py', 'Reference'),
        resolver_records={c.__name__: [f.name for f in fields(c)] for c in (Program, Reference, Symbol, Capture, FunctionPlan)},
        resolver_builtins=sorted(BUILTIN_NAMES), resolver_implemented=sorted(IMPLEMENTED_NAMES),
        native_extensions={k: asdict(v) for k, v in sorted(REGISTRY.extensions.items())},
        native_functions={k: asdict(v) for k, v in sorted(FUNCTIONS.items())}, pure_calls=sorted(PURE_CALLS),
        resource_policy=ResourcePolicy().effective_record(), resource_fingerprint=ResourcePolicy().fingerprint,
        diagnostics=sorted({node.value for p in ('zzy/diagnostics.py', 'zzy/resolver.py', 'zzy/interpreter.py')
            for node in ast.walk(ast.parse((ROOT / p).read_text(encoding='utf-8')))
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and len(node.value) == 4 and node.value.startswith('E') and node.value[1:].isdigit()}),
        manifests={p.relative_to(ROOT).as_posix(): [dict(id=c['id'], mode=c['mode'],
            file=c['file'], exit_code=c['exit_code']) for c in load_cases(p)] for p in DEFAULT_MANIFESTS},
        application_entrypoints=[p for p in ('apps/zzy-campus/main.zzy', 'apps/zzy-campus/limits.json',
            'examples/web/app.zzy', 'examples/sqlite/app.zzy', 'examples/contracts/app.zzy') if (ROOT / p).is_file()],
        host_entrypoints=['zzy.cli:main', 'zzy.web', 'zzy.embedding', 'zzy.contracts'],
        runtime_python_used=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', type=Path)
    args = parser.parse_args()
    record = snapshot()
    if args.check:
        previous = json.loads(args.check.read_text(encoding='utf-8'))
        # A later commit SHA alone does not change the frozen implementation.
        previous.pop('source_sha'); record.pop('source_sha')
        if json.loads(json.dumps(record)) != previous:
            raise SystemExit('Inventory drift: review the changed sources; do not regenerate golden expectations.')
    elif args.output:
        args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    else:
        parser.error('provide --output or --check')
    print(json.dumps(dict(ast_kinds=len(record['ast_kinds']), native_functions=len(record['native_functions']),
        manifests=len(record['manifests']), cases=sum(map(len, record['manifests'].values())))))


if __name__ == '__main__':
    main()
