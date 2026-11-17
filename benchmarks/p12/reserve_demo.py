"""Paired prototype test of a loop-based resource reservation precheck."""
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
from benchmarks.p12.run import expected
from benchmarks.run import environment
from zzy.process import run_bounded

CASES = [('X01', 10000), ('X02', 1000), ('X03', 1000)]
VARIANTS = ('baseline', 'reserve-loop')
WARMUPS, SAMPLES, SEED, TIMEOUT_SECONDS = 3, 15, 20261117, 30
INPUTS = ROOT/'benchmarks/results/p12/execute-stages/inputs'


def collect(case, n, variant, phase, index):
    path = (INPUTS/f'{case}-{n}.zzy').resolve()
    cmd = [sys.executable, '-X', 'utf8', '-m', 'benchmarks.p12.stage_worker',
           'zzy', case, str(n), str(path), '--variant', variant]
    row = dict(case=case, n=n, variant=variant, phase=phase, index=index,
               command=cmd, input_sha256=sha256(path.read_bytes()).hexdigest())
    started = perf_counter_ns()
    try:
        code, out, err = run_bounded(cmd, cwd=ROOT,
            env=dict(os.environ, PYTHONPATH=str(ROOT), PYTHONUTF8='1'),
            timeout=TIMEOUT_SECONDS, output_limit=1024*1024)
        row['parent_elapsed_ns'] = perf_counter_ns()-started
        row['exit_code'] = code
        record = json.loads(out)
        if (code != 0 or err or row['parent_elapsed_ns'] > TIMEOUT_SECONDS*1_000_000_000
                or record.get('status') != 'ok' or record.get('variant') != variant
                or record.get('source_sha256') != row['input_sha256']
                or record.get('value_sha256') != sha256(expected(case, n).encode()).hexdigest()):
            row.update(status='failure', stdout=out.decode('utf-8', errors='replace'),
                       stderr=err.decode('utf-8', errors='replace'))
        else:
            row.update(status='ok', execute_ns=record['timings']['execute_ns'],
                       timings=record['timings'])
    except subprocess.TimeoutExpired:
        row.update(status='timeout', parent_elapsed_ns=perf_counter_ns()-started)
    except Exception as error:
        row.update(status='error', parent_elapsed_ns=perf_counter_ns()-started,
                   error=f'{type(error).__name__}: {error}')
    return row


def summarize(rows):
    summary = []
    for case, n in CASES:
        samples = {}
        for variant in VARIANTS:
            selected = [r for r in rows if r['phase'] == 'sample' and r['case'] == case
                        and r['n'] == n and r['variant'] == variant and r['status'] == 'ok']
            values = [r['execute_ns']/1e6 for r in selected]
            samples[variant] = {r['index']: r['execute_ns'] for r in selected}
            item = dict(case=case, n=n, variant=variant, valid=len(values), planned=SAMPLES)
            if values:
                median = statistics.median(values)
                item.update(median_ms=median,
                    mad_ms=statistics.median(abs(v-median) for v in values),
                    min_ms=min(values), max_ms=max(values))
            summary.append(item)
        if len(samples['baseline']) == len(samples['reserve-loop']) == SAMPLES:
            paired = [(samples['reserve-loop'][i]/samples['baseline'][i]-1)*100
                      for i in range(SAMPLES)]
            summary.append(dict(case=case, n=n, variant='paired_change_percent',
                                valid=SAMPLES, median=statistics.median(paired),
                                mad=statistics.median(abs(v-statistics.median(paired)) for v in paired),
                                faster_pairs=sum(v < 0 for v in paired)))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = dict(cases=CASES, variants=VARIANTS, warmups=WARMUPS,
                    samples=SAMPLES, seed=SEED, timeout_seconds=TIMEOUT_SECONDS,
                    scope='one ZZY bench() call with fresh interpreter per child; no CLI startup',
                    candidate='loop precheck only, no runtime product change')
    (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    env = environment()
    env['demo_source_hashes'] = {name: sha256((ROOT/name).read_bytes()).hexdigest()
                                 for name in ('benchmarks/p12/stage_worker.py',
                                              'benchmarks/p12/reserve_demo.py')}
    (args.output/'environment.json').write_text(
        json.dumps(env, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    rows = []
    with (args.output/'raw.jsonl').open('w', encoding='utf-8') as stream:
        def write(row):
            row['order'] = len(rows)
            rows.append(row)
            stream.write(json.dumps(row, ensure_ascii=False)+'\n')
            stream.flush()

        for case, n in CASES:
            for variant in VARIANTS:
                write(collect(case, n, variant, 'equivalence', 0))
        if not any(r['status'] != 'ok' for r in rows):
            jobs = [(case, n, variant) for case, n in CASES for variant in VARIANTS]
            rng = random.Random(SEED)
            for phase, count in (('warmup', WARMUPS), ('sample', SAMPLES)):
                for index in range(count):
                    rng.shuffle(jobs)
                    for case, n, variant in jobs:
                        write(collect(case, n, variant, phase, index))
                    print(f'{phase} {index+1}/{count}', flush=True)
    report = dict(statistics=summarize(rows), failures=[r for r in rows
                  if r['status'] != 'ok'], total_records=len(rows))
    (args.output/'summary.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"records={len(rows)} failures={len(report['failures'])}", flush=True)
    return 1 if report['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
