"""Freeze and run Windows N7 benchmark rounds."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import sys
from time import perf_counter_ns

from benchmarks.n7.windows_metrics import counters
from zzy.resources import ResourcePolicy

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
WARMUPS, SAMPLES, TIMEOUT = 3, 15, 30
STAGES = ('read_ns', 'prepare_ns', 'init_ns', 'execute_ns', 'cleanup_ns')
EXPECTED_RELEASE = 'f697f08b0336bb34522ff036ca98cb7d72e2cf1adbb3993d940ae25e43279add'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def command(*argv):
    return subprocess.check_output(argv, cwd=ROOT, encoding='utf-8', errors='replace').strip()


def files_at(root):
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(root.rglob('*'))
            if p.is_file() and p.name != 'manifest.json'}


def machine():
    details = command('powershell.exe', '-NoProfile', '-Command',
                      '$c = Get-CimInstance Win32_Processor; '
                      '$m = Get-CimInstance Win32_ComputerSystem; '
                      '$o = Get-CimInstance Win32_OperatingSystem; '
                      '$p = Get-CimInstance Win32_Battery; '
                      '[pscustomobject]@{cpu=$c.Name; cores=$c.NumberOfCores; '
                      'logical=$c.NumberOfLogicalProcessors; ram=$m.TotalPhysicalMemory; '
                      'os=$o.Caption; build=$o.BuildNumber; battery=$p.BatteryStatus; '
                      'ac=(Get-CimInstance -Namespace root/wmi -ClassName BatteryStatus '
                      '-ErrorAction SilentlyContinue).PowerOnline} | ConvertTo-Json -Compress')
    power = command('powercfg', '/GETACTIVESCHEME')
    return dict(**json.loads(details), power_scheme=power.split()[3])


def freeze(folder, exe, probe):
    if digest(exe) != EXPECTED_RELEASE:
        raise ValueError('native binary differs from N6 Release')
    if platform.python_implementation() != 'CPython' or sys.version_info[:3] != (3, 12, 14):
        raise ValueError('N7 baseline requires the project CPython 3.12.14')
    if command('git', 'status', '--porcelain', '--', 'zzy'):
        raise ValueError('hosted ZZY differs from Git')
    python = Path(sys._base_executable).resolve()
    folder.mkdir(parents=True)
    shutil.copytree(ROOT/'zzy', folder/'zzy', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(exe, folder/'native.exe')
    shutil.copy2(probe, folder/'probe.exe')
    shutil.copy2(HERE/'worker.py', folder/'worker.py')
    shutil.copy2(HERE/'cases.json', folder/'cases.json')
    limits = ResourcePolicy().effective_record()
    save(folder/'limits.json', {k: limits[k] for k in ('policy_version', 'limits')})
    for case in json.loads((folder/'cases.json').read_bytes()):
        for ext, marker in [('zzy', '(zno) n := 10;'), ('py', 'n = 10\n')]:
            source = (ROOT/'benchmarks'/'p12'/f"{case['id']}.{ext}").read_text(encoding='utf-8')
            if case['n'] is not None:
                if source.count(marker) != 1:
                    raise ValueError(f'ambiguous input in {case["id"]}.{ext}')
                source = source.replace(marker, marker.replace('10', str(case['n'])))
            (folder/f"{case['id']}.{ext}").write_bytes(source.encode('utf-8'))
    deps = {str(path): digest(path) for path in [python, python.with_name('python312.dll'),
                                                python.with_name('python3.dll')]}
    env = environment(folder)
    policy = run_child([str(folder/'native.exe'), '--limits', 'limits.json', 'info'], folder, env)
    hosted = run_child([str(python), '-X', 'utf8', '-B', '-m', 'zzy', '--limits',
                        'limits.json', 'info'], folder, env)
    native_info = json.loads(policy['stdout'])
    hosted_info = json.loads(hosted['stdout'])
    if any(result['exit'] != 0 for result in (policy, hosted)) or any(
            info['resource_policy']['limits'] != limits['limits'] for info in (native_info, hosted_info)):
        raise ValueError('runtime policy differs from the frozen limit keys')
    save(folder/'manifest.json', dict(source_commit=command('git','rev-parse','HEAD'),
         hosted_tree=command('git','rev-parse','HEAD:zzy'), machine=machine(),
         cmake=command('cmake','--version').splitlines()[0], python=str(python), version=sys.version,
         python_deps=deps, limits=limits, native_info=native_info, hosted_info=hosted_info,
         rounding='Windows CPU ticks, nanoseconds; kernel working set and private commit peaks',
         timeout_s=TIMEOUT, warmups=WARMUPS, samples=SAMPLES, files=files_at(folder)))


def environment(folder):
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith('PYTHON')}
    return dict(env, PYTHONPATH=str(folder), PYTHONHASHSEED='0', PYTHONIOENCODING='utf-8')


def run_child(argv, cwd, env):
    start = perf_counter_ns()
    with subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as child:
        timeout = False
        try:
            out, err = child.communicate(timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            timeout = True
            child.kill()
            out, err = child.communicate()
        stopped = perf_counter_ns()
        try:
            metrics = counters(int(child._handle))
        except (OSError, RuntimeError) as error:
            metrics = {'metric_error': str(error)}
    return dict(command=argv, wall_ns=stopped-start, exit=child.returncode, timeout=timeout,
                stdout=out.decode('utf-8', errors='replace').replace('\r\n', '\n'),
                stderr=err.decode('utf-8', errors='replace').replace('\r\n', '\n'), **metrics)


def invocation(folder, python, case, variant, scope, candidate, logical=False):
    name = case['id']
    source = f'{name}.py' if variant == 'direct' else f'{name}.zzy'
    if variant in ('native', 'candidate'):
        bin_dir = folder if variant == 'native' else candidate
        if scope == 'cli':
            return [str(bin_dir/'native.exe'), '--limits', 'limits.json', 'run', source]
        return [str(bin_dir/'probe.exe'), source, 'limits.json']
    argv = [python, '-X', 'utf8', '-B']
    if scope == 'staged':
        return argv + ['worker.py', variant, source, 'limits.json'] + (['--logical'] if logical else [])
    if variant == 'hosted':
        return argv + ['-m', 'zzy', '--limits', 'limits.json', 'run', source]
    return argv + [source]


def check(row, case, scope):
    if row['timeout']:
        return 'timeout'
    if row['exit'] != 0 or row.get('metric_error') or row['stderr']:
        return 'error'
    stdout = row['stdout']
    if scope == 'staged':
        try:
            stage = json.loads(stdout)
            if any(type(stage[key]) is not int or stage[key] < 0 for key in STAGES) or stage['stderr']:
                return 'invalid-stages'
            row['stages'] = stage
            stdout = stage['stdout']
        except (ValueError, TypeError, KeyError):
            return 'invalid-stages'
    return 'ok' if stdout == case['stdout'] else 'wrong-answer'


def stat(values):
    values = sorted(values)
    median = statistics.median(values)
    quartiles = statistics.quantiles(values, n=4, method='inclusive')
    return dict(median=median, mad=statistics.median(abs(value-median) for value in values),
                q1=quartiles[0], q3=quartiles[2], min=values[0], max=values[-1])


def summarize(rows):
    groups = []
    for case, scope, variant in sorted({(r['case'], r['scope'], r['variant']) for r in rows}):
        matching = [r for r in rows if (r['case'], r['scope'], r['variant']) == (case, scope, variant)]
        good = [r for r in matching if not r['warmup'] and r['status'] == 'ok']
        totals = {state: sum(r['status'] == state for r in matching)
                  for state in sorted({r['status'] for r in matching})}
        measures = {key: stat([r[key] for r in good]) for key in (
            'wall_ns', 'cpu_ns', 'cpu_user_ns', 'cpu_kernel_ns', 'peak_working_set_bytes',
            'peak_private_bytes') if len(good) >= 2}
        if scope == 'staged' and len(good) >= 2:
            measures.update({key: stat([r['stages'][key] for r in good]) for key in STAGES})
        groups.append(dict(case=case, scope=scope, variant=variant, formal_ok=len(good),
                           statuses=totals, measures=measures))
    return groups


def verify(folder):
    manifest = json.loads((folder/'manifest.json').read_bytes())
    if (manifest['files'] != files_at(folder)
            or any(digest(p) != expected for p, expected in manifest['python_deps'].items())):
        raise ValueError('frozen artifacts changed')
    return manifest


def run(folder, output, seed, candidate=None, logical=False, smoke=False):
    manifest = verify(folder)
    output.mkdir(parents=True)
    save(output/'environment.json', dict(start=datetime.now(timezone.utc).isoformat(), seed=seed,
         machine=machine(), freeze_manifest_sha256=digest(folder/'manifest.json'),
         candidate=files_at(candidate) if candidate else None))
    rng = random.Random(seed)
    cases = json.loads((folder/'cases.json').read_bytes())
    env = environment(folder)
    rows = []
    variants = ('native', 'candidate') if candidate else ('native', 'hosted', 'direct')
    scopes = ('staged',) if logical else ('cli', 'staged')
    pairs = [(case, scope) for case in cases for scope in scopes]
    with (output/'raw.jsonl').open('x', encoding='utf-8') as stream:
        for index in range(1 if smoke or logical else WARMUPS+SAMPLES):
            rng.shuffle(pairs)
            for case, scope in pairs:
                pair = list(variants)
                rng.shuffle(pair)
                for variant in pair:
                    argv = invocation(folder, manifest['python'], case, variant, scope, candidate, logical)
                    row = run_child(argv, folder, env)
                    row.update(case=case['id'], scope=scope, variant=variant, sequence=index,
                               warmup=not (smoke or logical) and index < WARMUPS,
                               expected=case['stdout'], status=check(row, case, scope))
                    rows.append(row)
                    stream.write(json.dumps(row, ensure_ascii=False)+'\n')
                    stream.flush()
    verify(folder)
    if logical or smoke:
        save(output/'summary.json', [dict(case=r['case'], variant=r['variant'], status=r['status'],
             logical_peak=r.get('stages', {}).get('logical_peak')) for r in rows])
    else:
        save(output/'summary.json', summarize(rows))
    failures = [r for r in rows if r['status'] != 'ok']
    print(f'{output.name}: {len(rows)-len(failures)}/{len(rows)} correct, '
          f'{sum(r["timeout"] for r in failures)} timeouts', flush=True)
    return bool(failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='action', required=True)
    freezer = subs.add_parser('freeze')
    freezer.add_argument('folder', type=Path)
    freezer.add_argument('exe', type=Path)
    freezer.add_argument('probe', type=Path)
    runner = subs.add_parser('run')
    runner.add_argument('folder', type=Path)
    runner.add_argument('output', type=Path)
    runner.add_argument('--seed', type=int, required=True)
    runner.add_argument('--candidate', type=Path)
    modes = runner.add_mutually_exclusive_group()
    modes.add_argument('--logical', action='store_true')
    modes.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    if args.action == 'freeze':
        freeze(args.folder.resolve(), args.exe, args.probe)
        return 0
    return int(run(args.folder.resolve(), args.output, args.seed,
                   args.candidate.resolve() if args.candidate else None, args.logical, args.smoke))


if __name__ == '__main__':
    raise SystemExit(main())
