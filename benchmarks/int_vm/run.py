"""Validate and time the experimental VM against frozen N7 AST and CPython."""
import argparse
import json
from pathlib import Path
import random
import sys

from benchmarks.n7.run import digest, environment, machine, run_child, save, stat, verify

CASES = {
    'X00': ('X00', None, '314159\n'),
    'X01': ('X01', 10000, '333283335000\n'),
    'X02': ('X02', 10000, '49995000\n'),
    'X03': ('X03', 10000, '[10000, 49995000]\n'),
    'X03-40k': ('X03', 40000, '[40000, 799980000]\n'),
}


def smoke(run, exe, limits, output):
    sources = {
        'negative': ('(addnew) f(){(return) [-5 % 3, 5 % -3, -5 * -3];}io.print(f());', '[1, -1, 15]\n'),
        'bool': ('(addnew) f(){(return) (true) == 1;}io.print(f());', 'false\n'),
        'alias': ('(addnew) f(){(zno) a:=[];(zno) b:=a;array.push(b,42);(return) [len(a)];}io.print(f());', '[1]\n'),
        'overflow': ('(addnew) f(){(return) 1152921504606846975 + 1;}io.print(f());', '1152921504606846976\n'),
        'string': ('(addnew) f(){(return) "ok";}io.print(f());', 'ok\n'),
        'zero': ('(addnew) f(){(return) 1 % 0;}io.print(f());', None),
        'bad': ('(addnew) f(){(return) unknown;}io.print(f());', None),
    }
    rows = []

    def inspect(case, mode, expected_code, expected_output=None, backend=None, error=None, flags=(), policy=limits):
        file = output/'inputs'/f'{case}.zzy'
        row = run([exe, mode, str(file), str(policy), *flags])
        row.update(case=case, mode=mode)
        rows.append(row)
        save(output/'smoke.json', rows)
        if row['timeout'] or row['exit'] != expected_code:
            raise RuntimeError(row)
        if error is not None and error not in row['stderr']:
            raise RuntimeError(row)
        if expected_code == 0:
            result = json.loads(row['stdout'])
            if row['stderr'] or (result['backend'], result['stdout']) != (backend, expected_output):
                raise RuntimeError(row)

    for name, (source, answer) in sources.items():
        (output/'inputs'/f'{name}.zzy').write_text(source, encoding='utf-8')
        if name in ('negative', 'bool', 'alias'):
            inspect(name, 'vm', 0, answer, 'vm')
            inspect(name, 'ast', 0, answer, 'ast')
        elif name in ('overflow', 'string'):
            inspect(name, 'vm', 3, error='VM declined:')
            inspect(name, 'auto', 0, answer, 'ast')
        elif name == 'zero':
            inspect(name, 'vm', 3, error='zero divisor')
            inspect(name, 'auto', 1, error='E205')
        else:
            inspect(name, 'auto', 2, error='E302')
    inspect('X01', 'auto', 0, CASES['X01'][2], 'vm')
    inspect('X01', 'vm', 130, flags=('--cancel',))
    inspect('X01', 'auto', 130, flags=('--cancel',))
    reduced = output/'small-limit.json'
    save(reduced, {'policy_version': 1, 'limits': {'integer_bits': 18}})
    inspect('X01', 'vm', 3, error='custom resource policy', policy=reduced)
    inspect('X01', 'auto', 1, error='E211', policy=reduced)
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('frozen', type=Path)
    parser.add_argument('exe', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--seed', required=True, type=int)
    parser.add_argument('--smoke-only', action='store_true')
    args = parser.parse_args()
    frozen = args.frozen.resolve()
    exe = str(args.exe.resolve(strict=True))
    manifest = verify(frozen)
    output = args.output.resolve()
    limits = frozen/'limits.json'
    inputs = output/'inputs'
    inputs.mkdir(parents=True)
    env = environment(frozen)

    def run(argv):
        return run_child(argv, frozen, env)

    save(output/'environment.json', dict(machine=machine(), seed=args.seed, vm_sha256=digest(exe),
         n7_manifest_sha256=digest(frozen/'manifest.json'), python=manifest['version'],
         warmups=3, samples=15))
    for name, (source, n, _) in CASES.items():
        for ext in ('zzy', 'py'):
            raw = (frozen/f'{source}.{ext}').read_bytes()
            if n == 40000:
                marker = b'(zno) n := 10000;' if ext == 'zzy' else b'n = 10000\n'
                if raw.count(marker) != 1:
                    raise ValueError('expected exactly one input marker')
                raw = raw.replace(marker, marker.replace(b'10000', b'40000'))
            (inputs/f'{name}.{ext}').write_bytes(raw)
    print(f'guards and fixed answers: {smoke(run, exe, limits, output)} passed', flush=True)
    if args.smoke_only:
        return 0
    pairings = [(name, backend) for name in CASES for backend in ('vm', 'ast', 'python')]
    rng = random.Random(args.seed)
    groups = {key: [] for key in pairings}
    failures = 0
    with (output/'raw.jsonl').open('x', encoding='utf-8') as raw:
        for index in range(18):
            case_names = list(CASES)
            rng.shuffle(case_names)
            for name in case_names:
                backends = ['vm', 'ast', 'python']
                rng.shuffle(backends)
                for backend in backends:
                    zzy = str(inputs/f'{name}.zzy')
                    python = str(inputs/f'{name}.py')
                    if backend == 'vm':
                        argv = [exe, 'vm', zzy, str(limits)]
                    elif backend == 'ast':
                        argv = [str(frozen/'probe.exe'), zzy, str(limits)]
                    else:
                        argv = [manifest['python'], '-X', 'utf8', '-B', 'worker.py', 'direct', python, str(limits)]
                    row = run(argv)
                    answer = CASES[name][2]
                    row.update(case=name, backend=backend, warmup=index < 3, sample=index, expected=answer)
                    try:
                        payload = json.loads(row['stdout'])
                        passed = (row['exit'] == 0 and not row['timeout'] and not row['stderr']
                                  and 'metric_error' not in row and payload['stdout'] == answer
                                  and payload.get('backend') == ('vm' if backend == 'vm' else None)
                                  and type(payload['execute_ns']) is int and payload['execute_ns'] >= 0)
                    except (ValueError, KeyError, TypeError):
                        passed = False
                    row['passed'] = passed
                    raw.write(json.dumps(row, ensure_ascii=False)+'\n')
                    raw.flush()
                    if not passed:
                        failures += 1
                    if passed and index >= 3:
                        groups[(name, backend)].append(dict(row, stages=payload))
    if failures or any(len(rows) != 15 for rows in groups.values()):
        raise RuntimeError(f'{failures} failing samples or incomplete collection, see raw.jsonl')
    summary = []
    for (name, backend), rows in groups.items():
        fields = ('wall_ns', 'cpu_ns', 'peak_working_set_bytes', 'peak_private_bytes')
        phases = ('prepare_ns', 'execute_ns', 'lower_ns') if backend == 'vm' else ('prepare_ns', 'execute_ns')
        metrics = {key: stat([row[key] for row in rows]) for key in fields}
        metrics.update({key: stat([row['stages'][key] for row in rows]) for key in phases})
        summary.append(dict(case=name, backend=backend, metrics=metrics))
    verify(frozen)
    save(output/'summary.json', summary)
    print(f'{output.name}: {len(pairings)*15} formal samples, {len(pairings)*3} warmups', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
