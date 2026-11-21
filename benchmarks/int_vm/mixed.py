"""Exercise and measure per-function AST/VM dispatch on Windows."""
import argparse
import json
from pathlib import Path
from random import Random

from benchmarks.n7.run import digest, environment, machine, run_child, save, stat, verify

LOOP = '''
(addnew) square_sum(n) {
    (zyes) i := 0;
    (zyes) total := 0;
    (while) i < n { total <- total + i * i; i <- i + 1; }
    (return) total;
}
(addnew) main() {
    io.print("before");
    io.print(square_sum(10000));
    io.print("after");
}
main();
'''
SHORT = '''
(addnew) term(n) { (return) n * n + 3; }
(addnew) sum_many() {
    (zyes) i := 0;
    (zyes) total := 0;
    (while) i < 1000 { total <- total + term(8); i <- i + 1; }
    (return) total;
}
(addnew) main() {
    io.print(sum_many());
}
main();
'''
PY_LOOP = '''
def square_sum(n):
    i = total = 0
    while i < n:
        total += i * i
        i += 1
    return total

def main():
    print("before")
    print(square_sum(10000))
    print("after")

main()
'''
PY_SHORT = '''
def term(n):
    return n * n + 3

def sum_many():
    i = total = 0
    while i < 1000:
        total += term(8)
        i += 1
    return total

def main():
    print(sum_many())

main()
'''
TINY = '''
(addnew) twice(n) { (return) n * 2; }
(addnew) main() { io.print(twice(10)); }
main();
'''
PY_TINY = '''
def twice(n):
    return n * 2

def main():
    print(twice(10))

main()
'''


def shared_graph():
    zzy = ['(addnew) aux0(n) { (return) n+1; }']
    python = ['def aux0(n): return n+1']
    for i in range(1, 12):
        zzy.append(f'(addnew) aux{i}(n) {{ (return) aux{i-1}(n)+1; }}')
        python.append(f'def aux{i}(n): return aux{i-1}(n)+1')
    for i in range(48):
        zzy.append(f'(addnew) branch{i}(n) {{ (return) aux11(n); }}')
        python.append(f'def branch{i}(n): return aux11(n)')
    zzy.extend(['(addnew) total() {', '    (zyes) sum := 0;'])
    python.extend(['def total():', '    sum = 0'])
    for i in range(48):
        zzy.append(f'    sum <- sum + branch{i}(2);')
        python.append(f'    sum += branch{i}(2)')
    zzy.extend(['    (return) sum;', '}', '(addnew) main() { io.print(total()); }', 'main();'])
    python.extend(['    return sum', 'def main(): print(total())', 'main()'])
    return '\n'.join(zzy), '\n'.join(python)


CASES = {
    'loop': (LOOP, PY_LOOP, 'before\n333283335000\nafter\n', 'square_sum', 1),
    'short': (SHORT, PY_SHORT, '67000\n', 'sum_many', 1),
    'tiny': (TINY, PY_TINY, '20\n', 'twice', 1),
    'shared-graph': (*shared_graph(), '672\n', 'total', 1),
}


def smoke(invoke, output, default_limits):
    fixtures = output/'guards'
    fixtures.mkdir()
    custom = fixtures/'limits.json'
    save(custom, {'policy_version': 1, 'limits': {'integer_bits': 32}})
    body = '(addnew) worker(a, b) { (return) a * 10 + b; }'
    side_effects = body + '''
(addnew) arg(n) { io.print(n); (return) n; }
io.print(worker(arg(3),arg(4)));
'''
    chain = '(addnew) f0() { (return) 7; }\n' + '\n'.join(
        f'(addnew) f{i}() {{ (return) f{i-1}(); }}' for i in range(1, 64)
    )
    cases = (
        ('arguments', side_effects, default_limits, 0, '3\n4\n34\n', 1, 0, None),
        ('float', '(addnew) f(n){(return) n+1;}io.print(f(2.5));',
         default_limits, 0, '3.5\n', 0, 0, None),
        ('wide', '(addnew) f(n){(return) n+1;}io.print(f(1152921504606846976));',
         default_limits, 0, '1152921504606846977\n', 0, 0, None),
        ('overflow', '(addnew) f(n){(return) n+1;}io.print(f(1152921504606846975));',
         default_limits, 0, '1152921504606846976\n', 0, 1, None),
        ('io', '(addnew) f(n){io.print("inside");(return) n;}io.print(f(7));',
         default_limits, 0, 'inside\n7\n', 0, 0, None),
        ('zero', '(addnew) f(n){(return) 1 % n;} io.print("before"); io.print(f(0));',
         default_limits, 1, 'before\n', 0, 0, 'E205'),
        ('custom', LOOP, custom, 1, 'before\n', 0, 0, 'E211'),
        ('recursive', '(addnew) f(n){(zif?:) n==0{(return) 0;}(return) f(n-1);}'
         'io.print(f(5));', default_limits, 0, '0\n', 0, 0, None),
        ('array-alias', '(addnew) f(n){(zno)a:=[];(zno)b:=a;array.push(b,n);'
         '(return)len(a);}io.print(f(7));', default_limits, 0, '1\n', 0, 0, None),
        ('fused-overflow', '(addnew) f(a){ a <- a+1; (return) a; }'
         'io.print(f(1152921504606846975));', default_limits, 0, '1152921504606846976\n', 0, 1, None),
        ('fused-negative', '(addnew) f(a){ a <- a+1; (return) a; }io.print(f(-2));',
         default_limits, 0, '-1\n', 1, 0, None),
        ('subtraction-edge', '(addnew) f(a,b){ (return) a-b; }'
         'io.print(f(-1152921504606846975,1));', default_limits, 0, '-1152921504606846976\n', 0, 1, None),
        ('bool-arithmetic', '(addnew) f(a){ (zno) b:=a==1; (return) b+1; }'
         'io.print(f(1));', default_limits, 1, '', 0, 0, 'E201'),
        ('nested-error', '(addnew) f(a) { (return) 1%a; }(addnew) g(a) { (return) f(a); }'
         'io.print(g(0));', default_limits, 1, '', 0, 0, 'E205'),
        ('depth-64', chain+'\nio.print(f63());', default_limits, 0, '7\n', 1, 0, None),
        ('depth-65', chain+'\n(addnew) main(){ io.print(f63()); } main();',
         default_limits, 1, '', 0, 0, 'E211'),
    )
    records = []
    with (output/'guards.jsonl').open('x', encoding='utf-8') as stream:
        for name, source, limits, status, answer, vm_calls, retries, diagnostic in cases:
            file = fixtures/f'{name}.zzy'
            file.write_text(source, encoding='utf-8')
            ast = invoke('ast', file, limits)
            mixed = invoke('mixed', file, limits)
            stream.write(json.dumps(dict(name=name, ast=ast, mixed=mixed), ensure_ascii=False)+'\n')
            if any(row['timeout'] or row['exit'] != status for row in (ast, mixed)):
                raise RuntimeError(f'{name}: unexpected exit, see guards.jsonl')
            if status:
                if (ast['stdout'] != answer or mixed['stdout'] != answer
                        or ast['stderr'] != mixed['stderr'] or diagnostic not in mixed['stderr']):
                    raise RuntimeError(f'{name}: diagnostic or output mismatch')
            else:
                baseline, result = (json.loads(row['stdout']) for row in (ast, mixed))
                if (ast['stderr'] or mixed['stderr'] or baseline['stdout'] != answer
                        or result['stdout'] != answer or result['vm_calls'] != vm_calls
                        or result['vm_retries'] != retries):
                    raise RuntimeError(f'{name}: output or dispatch mismatch')
            records.append(name)
    helper_file = fixtures/'helper-graph.zzy'
    helper_file.write_text(SHORT, encoding='utf-8')
    helper_ast = invoke('ast', helper_file, default_limits)
    helper_mixed = invoke('mixed', helper_file, default_limits)
    with (output/'guards.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(dict(name='helper-graph', ast=helper_ast,
                                     mixed=helper_mixed), ensure_ascii=False)+'\n')
    helper_payload = json.loads(helper_mixed['stdout']) if helper_mixed['exit'] == 0 else {}
    if (helper_ast['exit'] != 0 or helper_mixed['exit'] != 0 or helper_ast['timeout']
            or helper_mixed['timeout'] or json.loads(helper_ast['stdout'])['stdout'] != '67000\n'
            or helper_payload.get('stdout') != '67000\n'
            or helper_payload.get('backend') != 'mixed'
            or helper_payload.get('function') != 'sum_many'
            or helper_payload.get('vm_calls') != 1
            or helper_payload.get('ast_calls') != 1
            or helper_payload.get('vm_retries') != 0
            or helper_payload.get('compiled_functions') != 2):
        raise RuntimeError('compiled helper call graph did not run as one mixed call')
    records.append('helper-graph')
    for name, expected_calls in (('loop', 1), ('tiny', 0), ('shared-graph', 0)):
        source, _, answer, _, _ = CASES[name]
        file = fixtures/f'auto-{name}.zzy'
        file.write_text(source, encoding='utf-8')
        auto = invoke('auto', file, default_limits)
        with (output/'guards.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(name=f'auto-{name}', auto=auto), ensure_ascii=False)+'\n')
        if auto['exit'] or auto['timeout'] or auto['stderr']:
            raise RuntimeError(f'auto-{name}: unexpected exit')
        payload = json.loads(auto['stdout'])
        if payload['stdout'] != answer or payload['vm_calls'] != expected_calls:
            raise RuntimeError(f'auto-{name}: unexpected dispatch or output')
        records.append(f'auto-{name}')
    cancel_source = fixtures/'cancel.zzy'
    cancel_source.write_text(LOOP, encoding='utf-8')
    cancelled = invoke('mixed', cancel_source, default_limits, '--cancel-vm')
    with (output/'guards.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(dict(name='cancel', mixed=cancelled), ensure_ascii=False)+'\n')
    if cancelled['timeout'] or cancelled['exit'] != 130 or cancelled['stdout'] != 'before\n':
        raise RuntimeError('expected cancellation inside VM without rerunning the caller')
    records.append('cancel')
    return len(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('frozen', type=Path)
    parser.add_argument('exe', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--seed', required=True, type=int)
    parser.add_argument('--smoke-only', action='store_true')
    parser.add_argument('--baseline', type=Path, help='frozen mixed probe for interleaved A/B')
    args = parser.parse_args()
    frozen, exe, output = (path.resolve() for path in (args.frozen, args.exe, args.output))
    manifest = verify(frozen)
    output.mkdir(parents=True)
    limits = frozen/'limits.json'
    env = environment(frozen)
    vm_hash = digest(exe)
    baseline = args.baseline.resolve() if args.baseline else None
    baseline_hash = digest(baseline) if baseline else None
    save(output/'environment.json', dict(machine=machine(), seed=args.seed, vm_sha256=vm_hash,
         baseline_sha256=baseline_hash,
         n7_manifest_sha256=digest(frozen/'manifest.json'), python=manifest['version'],
         warmups=3, samples=15))

    def invoke(mode, file, policy, *flags):
        return run_child([str(exe), mode, str(file), str(policy), *flags], frozen, env)

    print(f'mixed-call guards: {smoke(invoke, output, limits)} passed', flush=True)
    if args.smoke_only:
        return
    inputs = output/'inputs'
    inputs.mkdir()
    for case, (zzy, python, _, _, _) in CASES.items():
        (inputs/f'{case}.zzy').write_text(zzy, encoding='utf-8')
        (inputs/f'{case}.py').write_text(python, encoding='utf-8')
    variants = ('ast', 'mixed', 'python')
    if baseline:
        variants += ('baseline',)
    groups = {(case, variant): [] for case in CASES for variant in variants}
    rng = Random(args.seed)
    failures = 0
    with (output/'raw.jsonl').open('x', encoding='utf-8') as raw:
        for sample in range(18):
            names = list(CASES)
            rng.shuffle(names)
            for case in names:
                order = list(variants)
                rng.shuffle(order)
                _, _, expected, function, calls = CASES[case]
                for variant in order:
                    if variant == 'python':
                        row = run_child([manifest['python'], '-X', 'utf8', '-B', 'worker.py',
                                         'direct', str(inputs/f'{case}.py'), str(limits)], frozen, env)
                    elif variant == 'baseline':
                        row = run_child([str(baseline), 'mixed', str(inputs/f'{case}.zzy'),
                                         str(limits)], frozen, env)
                    else:
                        row = invoke(variant, inputs/f'{case}.zzy', limits)
                    try:
                        payload = json.loads(row['stdout'])
                        passed = (row['exit'] == 0 and not row['timeout'] and not row['stderr']
                                  and 'metric_error' not in row and not payload['stderr']
                                  and payload['stdout'] == expected and payload['execute_ns'] >= 0)
                        if variant in ('mixed', 'baseline'):
                            passed = (passed and payload['backend'] == 'mixed'
                                      and payload['function'] == function and payload['vm_calls'] == calls
                                      and payload['ast_calls'] == 1 and not payload['vm_retries'])
                        if variant == 'mixed' and case == 'shared-graph':
                            passed = passed and payload['compiled_functions'] == 61
                        if variant == 'ast':
                            passed = passed and payload['backend'] == 'ast' and not payload['vm_calls']
                    except (ValueError, KeyError, TypeError):
                        passed = False
                    row.update(case=case, variant=variant, sample=sample, warmup=sample<3,
                               expected=expected, passed=passed)
                    raw.write(json.dumps(row, ensure_ascii=False)+'\n')
                    raw.flush()
                    if not passed:
                        failures += 1
                    elif sample >= 3:
                        groups[case,variant].append(dict(row, stages=payload))
    if failures or any(len(rows) != 15 for rows in groups.values()):
        raise RuntimeError(f'{failures} failures or incomplete collection, see raw.jsonl')
    summary = []
    for (case, variant), rows in groups.items():
        keys = ('wall_ns', 'cpu_ns', 'peak_working_set_bytes', 'peak_private_bytes')
        metrics = {key: stat([row[key] for row in rows]) for key in keys}
        stages = ('prepare_ns', 'execute_ns') if variant == 'python' else ('prepare_ns', 'lower_ns', 'execute_ns')
        metrics.update({key: stat([row['stages'][key] for row in rows]) for key in stages})
        summary.append(dict(case=case, variant=variant, metrics=metrics))
    verify(frozen)
    if digest(exe) != vm_hash or (baseline and digest(baseline) != baseline_hash):
        raise RuntimeError('probe changed during sampling')
    save(output/'summary.json', summary)
    formal_samples = sum(len(rows) for rows in groups.values())
    print(f'{output.name}: {formal_samples} formal samples, '
          f'{len(groups) * 3} warmups, 0 failures', flush=True)


if __name__ == '__main__':
    main()
