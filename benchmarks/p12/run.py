"""External paired CLI measurement for the first P12 cross-runtime subset."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
from time import perf_counter_ns

from benchmarks.common import ROOT
from benchmarks.run import environment
from zzy.process import run_bounded

BASE = Path(__file__).resolve().parent
SIZES = {'X00': [None], 'X01': [1000, 10000],
         'X02': [100, 1000], 'X03': [100, 1000]}
SMALL = {'X00': [None], 'X01': [0, 1, 5],
         'X02': [0, 1, 5], 'X03': [0, 1, 5]}
WARMUPS, SAMPLES, TIMEOUT_SECONDS, SEED = 3, 15, 30, 20261117


def expected(case, n):
    if case == 'X00':
        return '314159'
    if case == 'X01':
        return str(n * (n - 1) * (2 * n - 1) // 6)
    if case == 'X02':
        return str(n * (n - 1) // 2 + n % 2)
    if case == 'X03':
        return f'[{n}, {n * (n - 1) // 2}]'
    raise ValueError(case)


def source(case, n, language):
    suffix = 'zzy' if language == 'zzy' else 'py'
    raw = (BASE / f'{case}.{suffix}').read_text(encoding='utf-8')
    if n is not None:
        marker = '(zno) n := 10;' if language == 'zzy' else 'n = 10'
        if raw.count(marker) != 1:
            raise ValueError(f'{case}/{language}: size marker')
        raw = raw.replace(marker, f'(zno) n := {n};' if language == 'zzy' else f'n = {n}')
    return raw.encode('utf-8')


def collect(case, n, language, path, phase, index):
    cmd = ([sys.executable, '-X', 'utf8', '-m', 'zzy', 'run', str(path)]
           if language == 'zzy' else [sys.executable, '-X', 'utf8', str(path)])
    row = dict(case=case, n=n, language=language, phase=phase, index=index, command=cmd)
    started = perf_counter_ns()
    try:
        code, out, err = run_bounded(cmd, cwd=ROOT,
            env=dict(os.environ, PYTHONPATH=str(ROOT), PYTHONUTF8='1'),
            timeout=TIMEOUT_SECONDS, output_limit=1024*1024)
        row.update(elapsed_ns=perf_counter_ns()-started, exit_code=code,
                   stdout_sha256=sha256(out).hexdigest())
        if row['elapsed_ns'] > TIMEOUT_SECONDS * 1_000_000_000:
            row.update(status='wall_budget_exceeded',
                       stdout=out.decode('utf-8', errors='replace'),
                       stderr=err.decode('utf-8', errors='replace'))
        elif code == 0 and not err and out.decode('utf-8').splitlines() == [expected(case, n)]:
            row['status'] = 'ok'
        else:
            row.update(status='wrong_result' if code == 0 else 'process_error',
                       stdout=out.decode('utf-8', errors='replace'),
                       stderr=err.decode('utf-8', errors='replace'))
    except subprocess.TimeoutExpired:
        row.update(status='timeout', elapsed_ns=perf_counter_ns()-started)
    except Exception as error:
        row.update(status='error', elapsed_ns=perf_counter_ns()-started,
                   error=f'{type(error).__name__}: {error}')
    return row


def summarize(rows):
    items = []
    for case, sizes in SIZES.items():
        for n in sizes:
            for language in ('zzy', 'python'):
                selected = [r for r in rows if r['phase'] == 'sample' and r['case'] == case
                            and r['n'] == n and r['language'] == language]
                values = [r['elapsed_ns']/1e6 for r in selected if r['status'] == 'ok']
                item = dict(case=case, n=n, language=language, valid=len(values), planned=SAMPLES)
                if values:
                    median = statistics.median(values)
                    item.update(median_ms=median, mad_ms=statistics.median(
                        abs(v-median) for v in values), min_ms=min(values), max_ms=max(values))
                items.append(item)
    return items


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    inputs = args.output / 'inputs'
    inputs.mkdir()
    manifest = dict(cases=SIZES, small_cases=SMALL, warmups=WARMUPS,
                    samples=SAMPLES, timeout_seconds=TIMEOUT_SECONDS, seed=SEED,
                    scope='full child CLI start to exit including streams',
                    cache='new process each run; OS page cache uncontrolled')
    (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    env = environment()
    env['template_hashes'] = {p.name: sha256(p.read_bytes()).hexdigest()
                              for p in sorted(BASE.glob('X0*.*'))}
    env['candidate_note'] = 'working tree candidate; Git HEAD alone is insufficient'
    (args.output/'environment.json').write_text(
        json.dumps(env, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    rows = []
    with (args.output/'raw.jsonl').open('w', encoding='utf-8') as stream:
        def write(row):
            row['order'] = len(rows)
            rows.append(row)
            stream.write(json.dumps(row, ensure_ascii=False)+'\n')
            stream.flush()

        # Fixed tiny inputs and independent formula gate formal samples.
        for case, sizes, phase in ((case, sizes, 'small') for case, sizes in SMALL.items()):
            for n in sizes:
                for language in ('zzy', 'python'):
                    suffix = 'zzy' if language == 'zzy' else 'py'
                    path = inputs/f'{case}-{phase}-{n}.{suffix}'
                    path.write_bytes(source(case, n, language))
                    write(collect(case, n, language, path.resolve(), phase, 0))
        for case, sizes in SIZES.items():
            for n in sizes:
                for language in ('zzy', 'python'):
                    suffix = 'zzy' if language == 'zzy' else 'py'
                    path = inputs/f'{case}-{n}.{suffix}'
                    path.write_bytes(source(case, n, language))
                    write(collect(case, n, language, path.resolve(), 'equivalence', 0))
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
                        write(collect(case, n, language, path, phase, index))
                    print(f'{phase} {index+1}/{count}: {len(jobs)} CLI runs', flush=True)
    report = dict(statistics=summarize(rows), failures=[row for row in rows
                  if row['status'] != 'ok'], total_records=len(rows))
    (args.output/'summary.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"records={len(rows)}, failures={len(report['failures'])}", flush=True)
    return 1 if report['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
