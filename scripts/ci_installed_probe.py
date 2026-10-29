"""Run only with the installed interpreter, -I and a cwd outside the checkout."""
import hashlib
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import zzy
from zzy.process import run_bounded


def main():
    source_root = Path(sys.argv[1]).resolve()
    work = Path.cwd().resolve()
    package = Path(zzy.__file__).resolve().parent
    assert not work.is_relative_to(source_root)
    assert package.is_relative_to(Path(sys.prefix).resolve())
    assert not package.is_relative_to(source_root)
    originals = {p.relative_to(source_root / 'zzy').as_posix(): p for p in (source_root / 'zzy').rglob('*.py')}
    installed = {p.relative_to(package).as_posix(): p for p in package.rglob('*.py')}
    assert originals.keys() == installed.keys()
    for name, path in originals.items():
        assert path.read_text(encoding='utf-8') == installed[name].read_text(encoding='utf-8'), name
    records = []
    def cli(*args, stdin='', status=0, stdout=None):
        command = [sys.executable, '-I', '-X', 'utf8', '-m', 'zzy', *args]
        env = dict(os.environ); env.pop('PYTHONPATH', None)
        code, out, err = run_bounded(command, cwd=work, env=env, stdin=stdin.encode(), timeout=30)
        records.append(dict(command=command, exit_code=code, stdout=out.decode(), stderr=err.decode()))
        assert code == status, records[-1]
        assert b'Traceback' not in err, records[-1]
        if status == 0: assert not err, records[-1]
        if stdout is not None: assert out.decode() == stdout, records[-1]
        return out.decode(), err.decode()

    (work/'db.zzy').write_text('(addnew) tx() { db.query("CREATE TABLE t(x)",[]); db.query("INSERT INTO t VALUES (?)",[7]); (return) (^_^)(db.query("SELECT x FROM t",[])); } io.print(db.transaction("installed.sqlite3",tx));',encoding='utf-8')
    cli('check','db.zzy',stdout=''); assert not (work/'installed.sqlite3').exists()
    cli('run','db.zzy',stdout='(^_^)([[7]])\n')
    cli('--help')
    out, _ = cli('info'); assert json.loads(out)['zzy_version'] == zzy.__version__
    (work / 'hello.zzy').write_text('io.print(2+3);', encoding='utf-8')
    cli('check', 'hello.zzy', stdout='')
    cli('run', 'hello.zzy', stdout='5\n')
    from zzy.embedding import load_module
    (work / 'embed.zzy').write_text('(addnew) identity(x) { (return) x; }', encoding='utf-8')
    with load_module(work / 'embed.zzy') as embedded:
        value = {'n': 2**100, 'items': [True, 1, None]}
        assert embedded.call('identity', value).value == value
    assert not any(name in sys.modules for name in ('starlette', 'uvicorn', 'tkinter'))
    (work / 'bad.zzy').write_text('io.print(total);', encoding='utf-8')
    out, err = cli('run', 'bad.zzy', '--diagnostic-format', 'json', status=2, stdout='')
    assert json.loads(err)['code'] == 'E302'
    (work / 'normal-spec.zzy').write_text('(spec) "sum" {(o_o)2+3==5;}', encoding='utf-8')
    out, _ = cli('test', 'normal-spec.zzy')
    assert json.loads(out.splitlines()[-1]) == dict(schema_version=1, tests=1, passed=1, failed=0, timed_out=0, collection_errors=0)
    source = '(zno)v:=io.input("input> ");io.print(v);io.write_text("effect.txt","effect");'
    (work / 'effects.zzy').write_text(source, encoding='utf-8')
    cli('check', 'effects.zzy', stdout=''); assert not (work / 'effect.txt').exists()
    cli('run', 'effects.zzy', stdin='hello\n', stdout='input> hello\n')
    assert (work / 'effect.txt').read_text() == 'effect'

    first = '''(zno)c:=sketch.canvas(100,100,"CI");(zno)p:=sketch.pen(c,"pen");
sketch.forward(p,10);sketch.copy_object(c,1);
io.print(sketch.save_svg(c,"drawing.svg"));
io.print(sketch.save_project(c,"saved.zzysketch"));
io.print(sketch.save_function(sketch.capture(c),"flower.zzy","flower"));'''
    second = '''(use) "flower.zzy" (as) lib;
(?_?)sketch.load_project("saved.zzysketch"){
(^_^)(c)=>{io.print(sketch.layer_info(c)[0].count);io.print(sketch.undo(c));
io.print(sketch.layer_info(c)[0].count);io.print(lib.flower(c,10,20,1,0));
io.print(sketch.layer_info(c)[0].count);}
(T_T)(m)=>{io.print(m);}}'''
    (work / 'save.zzy').write_text(first, encoding='utf-8')
    (work / 'load.zzy').write_text(second, encoding='utf-8')
    cli('check', 'save.zzy', stdout=''); assert not (work / 'saved.zzysketch').exists()
    cli('run', 'save.zzy', stdout='(^_^)(null)\n' * 3)
    assert ET.parse(work / 'drawing.svg').getroot().tag.endswith('svg')
    cli('run', 'load.zzy', stdout='2\ntrue\n1\n(^_^)(3)\n2\n')
    # Same installed process must remain headless; a separate probe avoids source imports.
    code = ('import sys;from zzy.cli import main;'
            'assert main(["run","hello.zzy"])==0;assert "tkinter" not in sys.modules')
    env = dict(os.environ); env.pop('PYTHONPATH', None)
    assert run_bounded([sys.executable, '-I', '-X', 'utf8', '-c', code], cwd=work, env=env) == (0, b'5\n', b'')

    app = ('app/main.zzy', '--limits', 'app/limits.json')
    cli('check', *app, stdout='')
    cli('run', *app, stdin='1\n2\n作业\n课程\n3\n1\n10\ntasks.json\n1\n0\n')
    expected = dict(schema_version=1, next_id=2, tasks=[dict(id=1, title='作业', category='课程', priority=3, done=False)])
    assert json.loads((work / 'tasks.json').read_text(encoding='utf-8')) == expected
    original = (work / 'tasks.json').read_bytes()
    out, _ = cli('run', *app, stdin='2\ntasks.json\n1\n0\n')
    assert '任务数=1 next_id=2 未保存=false' in out
    assert '1\t作业\t课程\t3\tfalse\n共1项\n' in out
    assert (work / 'tasks.json').read_bytes() == original
    report = dict(passed=True, installed_package=str(package), python=sys.version,
                  source_files=len(originals), headless=True, commands=records,
                  outputs={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in work.iterdir() if p.suffix in {'.svg', '.zzysketch', '.json'}})
    (work / 'probe.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(passed=True, source_files=len(originals), headless=True)))


if __name__ == '__main__':
    main()
