"""Independent N2 structure, no-execution, coordinate and output assertions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--exe', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        ap.error('do not overwrite evidence')
    exe = args.exe.resolve()
    records = []
    with tempfile.TemporaryDirectory(prefix='ZZY N2 观察 中文 ') as directory:
        folder = Path(directory)
        for path in (ROOT/'native_runtime/tests/program').glob('*.zzy'):
            shutil.copyfile(path, folder/path.name)

        def run(name, command, verify):
            item = dict(id=name, command=command, passed=False)
            try:
                p = subprocess.Popen([str(exe), *command, '--diagnostic-format=json'],
                    cwd=folder, env=dict(os.environ, PATH='', PYTHONPATH='bad-python-path'),
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                # Keep stdin open. A hidden io.input would hang instead of
                # seeing EOF and accidentally looking like a safe check.
                try:
                    if command[0] == 'check':
                        p.wait(timeout=5)
                    out, err = p.communicate(timeout=15)
                except subprocess.TimeoutExpired:
                    p.kill(); p.communicate(); raise
                item.update(exit_code=p.returncode, stdout=out.decode('utf-8'), stderr=err.decode('utf-8'))
                verify(p.returncode, out, err)
                item['passed'] = True
            except (AssertionError, ValueError, subprocess.TimeoutExpired) as e:
                item['failure'] = str(e)
            records.append(item)
            return item

        def ok(status, out, err):
            assert (status, out, err) == (0, b'', b''), 'quiet check without execution'

        run('no-execution-open-stdin', ['check', 'no-execute.zzy'], ok)
        assert not list(folder.glob('n2-*')), 'side-effect files unexpectedly created'

        def grammar(status, out, err):
            assert status == 0 and not err, 'program-info success'
            rows = [json.loads(line) for line in out.splitlines()]
            inventory = json.loads((ROOT/'native_runtime/tests/inventory.json').read_text(encoding='utf-8'))
            assert {r['kind'] for r in rows if r['record']=='node'} == set(inventory['ast_kinds']), 'all 56 AST kinds'
            assert rows[0]['execution'] is False and rows[0]['module_count'] == 2, 'whole graph metadata'
            ids = [r['id'] for r in rows if r['record']=='node']
            assert ids == list(range(rows[0]['node_count'])), 'stable contiguous IDs'
            for r in rows:
                if r['record']=='node':
                    assert all(c < r['id'] for c in r['children']), 'postorder immutable child indices'
            assert sum(r['record']=='import' for r in rows) == 1, 'import edge'
            assert sum(r['record']=='quantity' for r in rows) == 1, 'static quantity literal'
        first = run('all-syntax-layout', ['program-info', 'all-syntax.zzy'], grammar)
        second = run('deterministic-repeat', ['program-info', 'all-syntax.zzy'], grammar)
        records.append(dict(id='byte-repeatability', passed=first.get('stdout')==second.get('stdout') and bool(first.get('stdout'))))
        run('check-recovery-after-description', ['check', 'all-syntax.zzy'], ok)

        def failure(code, span, file=None, key=None):
            def verify(status, out, err):
                assert status == 2 and out == b'', 'atomic failure'
                lines = err.splitlines(); assert len(lines)==1, 'first error only'
                d=json.loads(lines[0]); assert d['kind']=='error' and d['code']==code, 'error code'
                actual = d['span']
                coords = None if actual is None else [actual['start']['line'],actual['start']['column'],actual['end']['line'],actual['end']['column']]
                assert coords==span, f'fixed source coordinates: {coords}'
                if file: assert d['file'].endswith(file), 'dependency source location'
                if key: assert key in d['message'], 'resource key'
            return verify

        (folder/'坐标.zzy').write_bytes(b'\xef\xbb\xbf'+('(zno) 名 := "😀";\r\n\tmissing;').encode('utf-8'))
        run('bom-crlf-tab-supplementary', ['check','坐标.zzy'], failure('E302',[2,2,2,9]))
        (folder/'eof.zzy').write_text('(zno) x := 1',encoding='utf-8')
        run('missing-semicolon-eof',['check','eof.zzy'],failure('E103',[1,13,1,13]))
        (folder/'first.zzy').write_text('missing;1 + ;',encoding='utf-8')
        run('whole-parser-before-resolver',['check','first.zzy'],failure('E103',[1,13,1,14]))
        (folder/'bad.zzy').write_text('(zno) 名 := missing;',encoding='utf-8')
        (folder/'entry.zzy').write_text('(use) "bad.zzy" (as) bad;',encoding='utf-8')
        run('dependency-coordinates',['check','entry.zzy'],failure('E302',[1,12,1,19],'bad.zzy'))
        (folder/'entry.zzy').write_text('(use) "absent.zzy" (as) bad;missing;',encoding='utf-8')
        run('parent-resolver-before-missing-import',['check','entry.zzy'],failure('E302',[1,29,1,36]))
        (folder/'bad.zzy').write_text('1;',encoding='utf-8')
        (folder/'entry.zzy').write_text('(use) "bad.zzy" (as) bad;',encoding='utf-8')
        (folder/'limits.json').write_text('{"policy_version":1,"limits":{"ast_nodes_total":4}}',encoding='utf-8')
        run('whole-graph-ast-budget',['check','entry.zzy','--limits','limits.json'],failure('E211',[1,1,1,2],'bad.zzy','ast_nodes_total'))
        # The first output record must be atomic. Later complete records may
        # remain after a stdout limit error; no partial JSON records allowed.
        (folder/'small.zzy').write_text('1;',encoding='utf-8')
        for limit in (1,128,1024):
            (folder/'limits.json').write_text(json.dumps({'policy_version':1,'limits':{'stdout_bytes':limit}}),encoding='utf-8')
            def output_boundary(status,out,err,limit=limit):
                assert status==2 and json.loads(err)['code']=='E211', 'description output limit'
                assert len(out)<=limit and (not out or out.endswith(b'\n')), 'complete records only'
                for line in out.splitlines(): json.loads(line)
            run('output-'+str(limit),['program-info','small.zzy','--limits','limits.json'],output_boundary)
        run('next-check-after-resource-error',['check','small.zzy'],ok)
        # No runtime typechecks, host signature checks, dead-code evaluation.
        (folder/'runtime.zzy').write_text('(zno) x:(Bool):=1;x<-2;len(1,2);(zif?:)(false){1/0;}',encoding='utf-8')
        run('runtime-errors-remain-runtime',['check','runtime.zzy'],ok)
        (folder/'recursive.zzy').write_text('(addnew) f(){(return)f();} f();',encoding='utf-8')
        run('recursive-function-not-called',['check','recursive.zzy'],ok)
    assert records, 'empty observation suite'
    report=dict(schema_version=1, scope='N2 independent fixed observer expectations; no execution oracle',
        exe=str(exe),exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
        total=len(records),passed=sum(r['passed'] for r in records),records=records)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"{report['passed']}/{report['total']} Program observer cases passed")
    for r in records:
        if not r['passed']: print(r['id'],r.get('failure'),r.get('stderr','')[:200])
    return int(report['passed']!=report['total'])


if __name__=='__main__':
    raise SystemExit(main())
