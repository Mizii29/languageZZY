"""Local and GitHub CI entry points. All reports belong to one checkout/run."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import tomllib
import unicodedata
import unittest
import venv

from .ci_logging import load_config, run_logged

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASELINE = ROOT / 'scripts/ci/test-inventory.json'
LOG_CONFIG = ROOT / 'docs/runtime/logging.json'
REQUIREMENT_SHA = 'b099c19fc339ce1dc1aab7e9d6c8126a9c5c9ace3d31b969a0623df90f521d2b'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').strip()


def files():
    names = subprocess.check_output(
        ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT)
    return sorted({s.decode('utf-8') for s in names.split(b'\0') if s
                   and not s.startswith(b'docs/manual-tests/')})


def fingerprint():
    digest = hashlib.sha256()
    for name in files():
        p = ROOT / name
        if p.is_file() and p.suffix in {'.py', '.zzy', '.json', '.toml', '.yml', '.ps1', '.txt'}:
            raw = p.read_bytes().replace(b'\r\n', b'\n')
            digest.update(name.encode() + b'\0' + hashlib.sha256(raw).digest())
    return digest.hexdigest()


def context():
    return dict(checkout_sha=git('rev-parse', 'HEAD'),
                head_sha=os.environ.get('CI_HEAD_SHA', ''), base_sha=os.environ.get('CI_BASE_SHA', ''),
                run_id=os.environ.get('GITHUB_RUN_ID', 'local'),
                attempt=os.environ.get('GITHUB_RUN_ATTEMPT', '1'),
                source_fingerprint=fingerprint())


def save(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def environment():
    from zzy.resources import ResourcePolicy
    config = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    if config['project']['requires-python'] != '==3.12.14':
        raise ValueError('Python support contract changed; review CI runtime lock first')
    if platform.python_implementation() != 'CPython' or sys.version_info[:3] != (3, 12, 14):
        raise ValueError('CI requires CPython 3.12.14 exactly')
    policy = ResourcePolicy()
    return dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
                unicode=unicodedata.unidata_version, git=git('--version'),
                runner_image=os.environ.get('ImageVersion', ''),
                resource_policy=policy.effective_record(), resource_fingerprint=policy.fingerprint)


def inventory():
    from tests.blackbox import DEFAULT_MANIFESTS, load_cases
    def flatten(suite):
        for test in suite:
            if isinstance(test, unittest.TestSuite):
                yield from flatten(test)
            else:
                if isinstance(test, unittest.loader._FailedTest):
                    raise ValueError(f'Test import failed: {test.id()}')
                yield test.id()
    ids = sorted(flatten(unittest.defaultTestLoader.discover(str(ROOT / 'tests'), top_level_dir=str(ROOT))))
    cases = {}; seen = set()
    for path in DEFAULT_MANIFESTS:
        entries = load_cases(path)
        keys = sorted(f"{c['mode']}_cli.{c['id']}" for c in entries)
        if seen.intersection(keys):
            raise ValueError('Duplicate blackbox identity across manifests')
        for case in entries:
            check_fixture(case)
        seen.update(keys)
        cases[path.relative_to(ROOT).as_posix()] = keys
    # P09 intentionally repeats 23 existing CLI cases under its application policy.
    if not ids or not seen.issubset(ids):
        raise ValueError('Empty or incompletely collected test inventory')
    return dict(test_ids=ids, manifests=cases, collected=len(ids), blackbox=len(seen))


def check_fixture(case):
    diagnostic = case.get('diagnostic', {})
    expected_missing = (case['exit_code'] == 2 and diagnostic.get('code') == 'E401'
                        and 'span' in diagnostic and diagnostic['span'] is None)
    if not (ROOT / case['cwd'] / case['file']).is_file() and not expected_missing:
        raise ValueError(f"Missing fixture: {case['file']}")


def check_inventory(current, baseline):
    missing = Counter(baseline['test_ids']) - Counter(current['test_ids'])
    if missing:
        raise ValueError(f'Test inventory shrank: {sorted(missing)[:8]}')
    for name, ids in baseline['manifests'].items():
        if not set(ids).issubset(current['manifests'].get(name, [])):
            raise ValueError(f'Blackbox manifest shrank or moved: {name}')


def check_markdown():
    count = links = 0
    for name in files():
        if not name.endswith('.md'):
            continue
        count += 1; fence = None
        for number, line in enumerate((ROOT / name).read_text(encoding='utf-8').splitlines(), 1):
            marker = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
            if marker:
                token = marker[1]
                if fence is None: fence = token
                elif token[0] == fence[0] and len(token) >= len(fence): fence = None
                continue
            if fence:
                continue
            for match in re.finditer(r'\]\((<[^>]+>|[^)\s]+)(?:\s+"[^"]*")?\)', line):
                target = match[1].strip('<>')
                if re.match(r'^[a-zA-Z][\w+.-]*:', target) or target.startswith('#'):
                    continue
                from urllib.parse import unquote
                target = unquote(target.split('#', 1)[0])
                if target:
                    links += 1
                    if not (ROOT / name).parent.joinpath(target).exists():
                        raise ValueError(f'{name}:{number}: broken local link {target}')
        if fence:
            raise ValueError(f'{name}: unclosed code fence')
    return dict(markdown_files=count, local_links=links)


def command(record, args, *, cwd=ROOT, stdin=b'', timeout=120):
    from zzy.process import run_bounded
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    env.pop('PYTHONPATH', None)
    status, out, err = run_bounded([str(a) for a in args], cwd=cwd, env=env,
                                   stdin=stdin, timeout=timeout, output_limit=8 * 1024**2)
    entry = dict(command=[str(a) for a in args], cwd=str(cwd), exit_code=status,
                 stdout=out.decode('utf-8', errors='backslashreplace'),
                 stderr=err.decode('utf-8', errors='backslashreplace'))
    record.setdefault('commands', []).append(entry)
    return status, out, err


def require_ok(result):
    if result[0]:
        raise ValueError(f'Command failed ({result[0]}): {result[2].decode("utf-8")}')
    return result


def static(record, output):
    record.update(environment=environment())
    record['log_config'] = vars(load_config(LOG_CONFIG))
    if hashlib.sha256((ROOT / 'docs/requirement.md').read_bytes()).hexdigest() != REQUIREMENT_SHA:
        raise ValueError('Assignment requirement bytes changed')
    record['inventory'] = inventory()
    check_inventory(record['inventory'], json.loads(BASELINE.read_text(encoding='utf-8')))
    record.update(check_markdown())
    require_ok(command(record, ['git', 'diff', '--check']))
    for name in files():
        if name.startswith(('scripts/', '.github/')) and Path(name).suffix in {'.py', '.json', '.ps1', '.txt', '.yml'}:
            for number, line in enumerate((ROOT / name).read_text(encoding='utf-8').splitlines(), 1):
                if line.rstrip() != line:
                    raise ValueError(f'{name}:{number}: trailing whitespace')
    require_ok(command(record, [sys.executable, '-X', 'utf8', '-m', 'tests.p09.count_lines', '--check']))


def validate_suite(report, expected):
    if (report.get('passed') is not True or type(report.get('collected')) is not int
            or report['collected'] <= 0 or report['collected'] != expected
            or report.get('tests_run') != expected
            or any(report.get(k) != 0 for k in ('failures', 'errors', 'skipped', 'expected_failures'))):
        raise ValueError('Missing, incomplete or unsuccessful suite report')


def regression(record, output):
    record.update(environment=environment())
    before = inventory()
    check_inventory(before, json.loads(BASELINE.read_text(encoding='utf-8')))
    destination = output / 'all-tests.json'
    config = load_config(LOG_CONFIG)
    record['log'] = dict(config_file=LOG_CONFIG.relative_to(ROOT).as_posix(),
                        config=vars(config), encoding='utf-8', compression='gzip')
    try:
        status = run_logged([sys.executable, '-X', 'utf8', '-m', 'tests', '--report', str(destination)],
                            cwd=ROOT, path=output / 'tests.log', config=config, timeout=40 * 60,
                            stats=record['log'])
    finally:
        record['log']['files'] = sorted(p.name for p in output.glob('tests.log*'))
    record['suite_exit_code'] = status
    record['suite'] = json.loads(destination.read_text(encoding='utf-8'))
    if status:
        raise ValueError(f'Full regression failed ({status}); see tests.log and rotated .gz logs')
    validate_suite(record['suite'], before['collected'])
    if before != inventory():
        raise ValueError('Test inventory changed during execution')
    record['collected'] = before['collected']


def package(record, output, installer):
    record.update(environment=environment())
    wheel_dir = output / 'wheel'; wheel_dir.mkdir()
    require_ok(command(record, [installer, '-X', 'utf8', '-m', 'pip', 'wheel', ROOT,
                               '--no-deps', '--no-build-isolation', '--no-index', '--no-cache-dir',
                               '--wheel-dir', wheel_dir]))
    wheels = list(wheel_dir.glob('zzy_language-*.whl'))
    if len(wheels) != 1:
        raise ValueError('Expected exactly one project wheel')
    record['wheel_sha256'] = hashlib.sha256(wheels[0].read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='ZZY CI 中文 安装 ') as directory:
        temp = Path(directory); env = temp / '环境'; cwd = temp / '中文 空格 工作目录'; cwd.mkdir()
        venv.EnvBuilder(with_pip=False).create(env)
        python = env / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        require_ok(command(record, [installer, '-X', 'utf8', '-m', 'pip', '--python', python, 'install',
                                   '--no-index', '--no-deps', wheels[0]], cwd=cwd))
        import shutil
        shutil.copyfile(ROOT / 'scripts/ci_installed_probe.py', cwd / 'installed_probe.py')
        shutil.copytree(ROOT / 'apps/zzy-campus', cwd / 'app')
        require_ok(command(record, [python, '-I', '-X', 'utf8', cwd / 'installed_probe.py', ROOT],
                           cwd=cwd, timeout=180))
        record['probe'] = json.loads((cwd / 'probe.json').read_text(encoding='utf-8'))
        if record['probe'].get('passed') is not True:
            raise ValueError('Installed probe did not pass')
        save(output / 'probe.json', record['probe'])


def validate_gate(reports, expected):
    for kind in ('static', 'regression', 'package'):
        report = reports[kind]
        if report.get('kind') != kind or report.get('passed') is not True or report.get('context') != expected:
            raise ValueError(f'{kind}: failed, stale or mismatched report')
    validate_suite(reports['regression']['suite'], reports['static']['inventory']['collected'])
    if reports['package'].get('probe', {}).get('passed') is not True:
        raise ValueError('Missing installed package proof')


def gate(record, artifacts):
    statuses = os.environ.get('CI_NEEDS_RESULTS')
    if statuses and any(value.get('result') != 'success' for value in json.loads(statuses).values()):
        raise ValueError('An upstream job failed, was skipped or was cancelled')
    reports = {kind: json.loads((artifacts / kind / 'report.json').read_text(encoding='utf-8'))
               for kind in ('static', 'regression', 'package')}
    validate_gate(reports, record['context'])
    record['jobs'] = {kind: report['passed'] for kind, report in reports.items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=('static', 'regression', 'package', 'gate', 'inventory'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--artifacts', type=Path)
    parser.add_argument('--installer', type=Path, default=Path(sys.executable))
    args = parser.parse_args(argv)
    if args.kind == 'inventory':
        save(BASELINE, inventory()); print(BASELINE); return 0
    if args.output is None:
        parser.error('--output is required')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    record = dict(schema_version=1, kind=args.kind, passed=False,
                  started_at=datetime.now(timezone.utc).isoformat())
    try:
        record['context'] = context()
        if args.kind == 'static': static(record, output)
        elif args.kind == 'regression': regression(record, output)
        elif args.kind == 'package': package(record, output, args.installer.resolve())
        else:
            if args.artifacts is None: raise ValueError('--artifacts is required for gate')
            gate(record, args.artifacts)
        if context() != record['context']:
            raise ValueError('Checkout/context changed during CI job')
        record['passed'] = True
    except (Exception, KeyboardInterrupt) as error:
        record['error'] = f'{type(error).__name__}: {error}'
        print(record['error'], file=sys.stderr)
    finally:
        record['finished_at'] = datetime.now(timezone.utc).isoformat()
        save(output / 'report.json', record)
    print(json.dumps({k: record[k] for k in ('kind', 'passed')}, ensure_ascii=False))
    return 0 if record['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
