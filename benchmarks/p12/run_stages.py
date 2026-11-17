"""Collect paired, batched prepare/initialize/execute timings for X00-X03."""
import argparse
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
from time import perf_counter_ns

from benchmarks.common import ROOT
from benchmarks.p12.run import SIZES, SMALL, SAMPLES, SEED, TIMEOUT_SECONDS, WARMUPS, expected, source
from benchmarks.run import environment
from zzy.process import run_bounded

BASE = Path(__file__).resolve().parent
PHASES = ('read', 'prepare', 'initialize', 'execute', 'validate', 'cleanup')


def wall_budget_exceeded(elapsed_ns):
    return elapsed_ns > TIMEOUT_SECONDS * 1_000_000_000


def collect(case, n, language, path, phase, index, batch=1):
    command = [sys.executable, '-X', 'utf8', '-m', 'benchmarks.p12.stage_worker',
               language, case, 'none' if n is None else str(n), str(path),
               '--batch', str(batch)]
    row = dict(case=case, n=n, language=language, phase=phase, index=index,
               batch=batch, command=command)
    start = perf_counter_ns()
    try:
        code, out, err = run_bounded(command, cwd=ROOT,
            env=dict(os.environ, PYTHONPATH=str(ROOT), PYTHONUTF8='1'),
            timeout=TIMEOUT_SECONDS, output_limit=1024*1024)
        row['parent_elapsed_ns'] = perf_counter_ns() - start
        row['exit_code'] = code
        result = json.loads(out)
        if wall_budget_exceeded(row['parent_elapsed_ns']):
            row.update(status='wall_budget_exceeded', worker_status=result.get('status'),
                       worker_timings=result.get('timings'),
                       stderr=err.decode('utf-8', errors='replace'))
        elif (code != 0 or err or result.get('status') != 'ok'
                or result.get('batch') != batch
                or result.get('value_sha256') != sha256(expected(case, n).encode()).hexdigest()
                or any(type(result.get('timings', {}).get(f'{name}_ns')) is not int
                       or result['timings'][f'{name}_ns'] < 0 for name in PHASES)):
            row.update(status='failure', stdout=out.decode('utf-8', errors='replace'),
                       stderr=err.decode('utf-8', errors='replace'))
        else:
            row.update(status='ok', timings=result['timings'],
                       source_sha256=result['source_sha256'],
                       value_sha256=result['value_sha256'])
    except subprocess.TimeoutExpired:
        row.update(status='timeout', parent_elapsed_ns=perf_counter_ns()-start)
    except Exception as error:
        row.update(status='error', parent_elapsed_ns=perf_counter_ns()-start,
                   error=f'{type(error).__name__}: {error}')
    return row


def batch_size(row):
    times = row['timings']
    execute = max(1, times['execute_ns'])
    per_call = max(1, sum(times[f'{name}_ns'] for name in PHASES[2:]))
    return max(1, min(100000, math.ceil(50_000_000/execute),
                      int(1_000_000_000/per_call)))


def summarize(rows):
    result = []
    for case, sizes in SIZES.items():
        for n in sizes:
            for language in ('zzy', 'python'):
                selected = [r for r in rows if r['phase'] == 'sample'
                            and r['case'] == case and r['n'] == n
                            and r['language'] == language]
                for scope in PHASES:
                    values = [r['timings'][f'{scope}_ns'] /
                              (1 if scope in ('read', 'prepare') else r['batch']) / 1e6
                              for r in selected if r['status'] == 'ok']
                    item = dict(case=case, n=n, language=language, scope=scope,
                                valid=len(values), planned=SAMPLES)
                    if values:
                        median = statistics.median(values)
                        item.update(median_ms=median,
                            mad_ms=statistics.median(abs(v-median) for v in values),
                            min_ms=min(values), max_ms=max(values))
                    result.append(item)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    inputs = args.output/'inputs'
    inputs.mkdir()
    manifest = dict(cases=SIZES, small_cases=SMALL, warmups=WARMUPS,
                    samples=SAMPLES, seed=SEED, timeout_seconds=TIMEOUT_SECONDS,
                    batch='preflight target 50ms execute, max 1s total and 100000 calls',
                    scope='source read; prepare; fresh context initialization; '
                          'bench() call; result validation; cleanup',
                    exclusions='child process startup and output JSON excluded from inner phases')
    (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    env = environment()
    env['benchmark_hashes'] = {p.name: sha256(p.read_bytes()).hexdigest()
                               for p in sorted(BASE.glob('*.py'))}
    env['template_hashes'] = {p.name: sha256(p.read_bytes()).hexdigest()
                              for p in sorted(BASE.glob('X0*.*'))}
    (args.output/'environment.json').write_text(
        json.dumps(env, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    rows, batches = [], {}
    with (args.output/'raw.jsonl').open('w', encoding='utf-8') as stream:
        def write(row):
            row['order'] = len(rows)
            rows.append(row)
            stream.write(json.dumps(row, ensure_ascii=False)+'\n')
            stream.flush()

        for case, sizes in SMALL.items():
            for n in sizes:
                for language in ('zzy', 'python'):
                    suffix = 'zzy' if language == 'zzy' else 'py'
                    path = inputs/f'{case}-small-{n}.{suffix}'
                    path.write_bytes(source(case, n, language))
                    write(collect(case, n, language, path.resolve(), 'small', 0))
        for case, sizes in SIZES.items():
            for n in sizes:
                for language in ('zzy', 'python'):
                    suffix = 'zzy' if language == 'zzy' else 'py'
                    path = inputs/f'{case}-{n}.{suffix}'
                    path.write_bytes(source(case, n, language))
                    row = collect(case, n, language, path.resolve(), 'equivalence', 0)
                    write(row)
                    if row['status'] == 'ok':
                        batches[case, n, language] = batch_size(row)
        (args.output/'batches.json').write_text(json.dumps([
            dict(case=case, n=n, language=language, batch=batch)
            for (case, n, language), batch in batches.items()], indent=2)+'\n', encoding='utf-8')
        if not any(row['status'] != 'ok' for row in rows) and not args.verify_only:
            jobs = [(case, n, language) for case, sizes in SIZES.items()
                    for n in sizes for language in ('zzy', 'python')]
            rng = random.Random(SEED)
            for phase, count in (('warmup', WARMUPS), ('sample', SAMPLES)):
                for index in range(count):
                    rng.shuffle(jobs)
                    for case, n, language in jobs:
                        suffix = 'zzy' if language == 'zzy' else 'py'
                        path = (inputs/f'{case}-{n}.{suffix}').resolve()
                        write(collect(case, n, language, path, phase, index,
                                      batches[case, n, language]))
                    print(f'{phase} {index+1}/{count}: {len(jobs)} stage runs', flush=True)
    report = dict(statistics=summarize(rows), failures=[r for r in rows
                  if r['status'] != 'ok'], total_records=len(rows))
    (args.output/'summary.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"records={len(rows)}, failures={len(report['failures'])}", flush=True)
    return 1 if report['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
