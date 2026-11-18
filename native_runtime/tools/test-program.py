"""N2 native check against retained, independent external expectations.

This coordinator never calls the Python backend to manufacture answers.
Each native child has empty PATH and invalid PYTHONPATH. No empty success.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('do not overwrite evidence')
    exe = args.exe.resolve()
    inventory = json.loads((ROOT / 'native_runtime/tests/inventory.json').read_text(encoding='utf-8'))
    manifests = json.loads((ROOT / 'native_runtime/tests/program/manifests.json').read_text(encoding='utf-8'))
    assert manifests == list(inventory['manifests']), 'frozen manifest collection drift'
    records = []
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='ZZY N2 check 中文 ') as temporary:
        limits = Path(temporary) / 'limits.json'
        for manifest in manifests:
            for case in json.loads((ROOT / manifest).read_text(encoding='utf-8'))['cases']:
                if case['mode'] != 'check':
                    continue
                command = [str(exe), 'check', case['file'], '--diagnostic-format=json']
                if 'limits' in case:
                    limits.write_text(json.dumps({'policy_version': 1, 'limits': case['limits']}), encoding='utf-8')
                    command += ['--limits', str(limits)]
                item = dict(manifest=manifest, id=case['id'], command=command,
                            expected_exit=case['exit_code'], passed=False)
                try:
                    process = subprocess.run(command, cwd=ROOT / case['cwd'],
                        input=case.get('stdin', '').encode('utf-8'),
                        env=dict(os.environ, PATH='', PYTHONPATH='invalid-native-python'),
                        capture_output=True, timeout=case['timeout_seconds'])
                    out, err = process.stdout.decode('utf-8'), process.stderr.decode('utf-8')
                    item.update(exit_code=process.returncode, stdout=out, stderr=err, timed_out=False)
                    assert process.returncode == case['exit_code'], 'exit code'
                    assert out == case['stdout'], 'stdout'
                    expected = case.get('diagnostic')
                    if expected:
                        lines = err.splitlines()
                        assert len(lines) == 1, 'first error only'
                        d = json.loads(lines[0])
                        assert set(d) == {'schema_version', 'kind', 'code', 'file', 'span', 'message', 'notes'}, 'diagnostic fields'
                        assert d['schema_version'] == 1 and d['kind'] == 'error', 'diagnostic schema'
                        assert d['code'] == expected['code'], 'code'
                        span = d['span']
                        actual = None if span is None else [span['start']['line'], span['start']['column'], span['end']['line'], span['end']['column']]
                        assert actual == expected['span'], 'span'
                        if 'file' in expected:
                            assert d['file'] and d['file'].replace('\\', '/').endswith(expected['file'].replace('\\', '/')), 'file'
                        if 'message_contains' in expected:
                            assert expected['message_contains'] in d['message'], 'message contains'
                        if 'notes' in expected:
                            assert d['notes'] == expected['notes'], 'notes'
                    else:
                        assert err == '', 'unexpected stderr'
                    item['passed'] = True
                except (AssertionError, ValueError, subprocess.TimeoutExpired) as error:
                    item['failure'] = str(error)
                records.append(item)
    assert records, 'empty test collection'
    report = dict(schema_version=1, scope='N2 retained check manifests, no execution',
        executable=str(exe), executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
        elapsed_seconds=time.perf_counter()-start, total=len(records),
        passed=sum(r['passed'] for r in records), cases=records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"{report['passed']}/{report['total']} native check cases passed")
    for record in records:
        if not record['passed']:
            print(record['manifest'], record['id'], record.get('failure'), record.get('stderr', '')[:400])
    return int(report['passed'] != report['total'])


if __name__ == '__main__':
    raise SystemExit(main())
