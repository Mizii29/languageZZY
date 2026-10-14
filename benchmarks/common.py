"""Manifest validation, deterministic source generation and independent oracles."""
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from zzy.resources import ResourcePolicy

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'benchmarks'
POLICY = ResourcePolicy()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_manifest(path=BASE / 'cases.json'):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate manifest key: '+key)
            result[key] = value
        return result
    manifest = json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)
    if type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1:
        raise ValueError('invalid manifest schema')
    cases = manifest.get('cases')
    if not isinstance(cases, list) or len(cases) != 9 or {c['id'] for c in cases} != {f'B{i:02}' for i in range(1, 10)}:
        raise ValueError('exactly B01-B09 required; empty/partial/duplicate collection fails')
    required = {'id','category','zzy_file','python_file','algorithm','sizes','input_definition',
                'expected_result','timing_scopes','setup','reset','teardown','warmups','samples',
                'sample_timeout_seconds','resource_policy','resource_fingerprint'}
    for case in cases:
        if not required <= case.keys():
            raise ValueError('missing manifest fields')
        if case['sizes'] != ([100,1000,10000] if case['id']=='B06' else [1000,10000,100000]):
            raise ValueError('contract sizes changed')
        if case['warmups'] != 3 or case['samples'] != 15 or case['sample_timeout_seconds'] != 30:
            raise ValueError('contract baseline sampling changed')
        if case['resource_fingerprint'] != POLICY.fingerprint or case['resource_policy'] != POLICY.effective_record():
            raise ValueError('effective resource policy differs from manifest')
        for key in ('zzy_file', 'python_file'):
            file = (ROOT / case[key]).resolve()
            if not file.is_relative_to(BASE) or not file.is_file():
                raise ValueError('missing/unsafe paired file')
    return manifest


def source(case, language, n):
    if type(n) is not int or n < (1 if case['id']=='B06' else 0):
        raise ValueError('invalid input size')
    raw = (ROOT / case[language+'_file']).read_text(encoding='utf-8')
    if case['id'] == 'B06':
        if language == 'zzy':
            raw = '(addnew) bench() {\n'+''.join(f'    (zno) value{i} := {i};\n' for i in range(n))+f'    (return) value{n-1};\n}}\nio.print(bench());\n'
        else:
            raw = 'def bench():\n'+''.join(f'    value{i} = {i}\n' for i in range(n))+f'    return value{n-1}\n\n\nif __name__ == \'__main__\':\n    print(bench())\n'
    else:
        marker = '(zno) n := 10;' if language == 'zzy' else 'n = 10\n'
        if raw.count(marker) != 1:
            raise ValueError('size marker missing or ambiguous')
        raw = raw.replace(marker, f'(zno) n := {n};' if language=='zzy' else f'n = {n}\n')
    return raw.encode('utf-8')


def expected(case_id, n):
    if case_id in {'B01','B03','B04'}:
        return n*(n-1)//2
    if case_id == 'B02':
        return n*(n+1)//2
    if case_id == 'B05':
        # Counting oracle, independent of the measured comparison sort.
        counts = Counter((n-1-i)%97 for i in range(n))
        return [value for value in range(97) for _ in range(counts[value])]
    if case_id == 'B06':
        return n-1
    if case_id == 'B07':
        # Priority buckets, independent of the measured stable comparison sort.
        return [i for priority in range(4,-1,-1) for i in range(n)
                if i%3 != 0 and i%5 == priority][:10]
    if case_id == 'B08':
        return [n, 'a' if n%2==0 else 'b']
    if case_id == 'B09':
        number = Fraction(n,1000)
        return [number.numerator, number.denominator, [0,1]]
    raise ValueError(case_id)


def expected_stdout(case_id, n):
    answer = expected(case_id, n)
    if case_id == 'B08':
        return f'[{answer[0]}, {answer[1]}]\n'.encode()
    if case_id == 'B09':
        return f'{Fraction(answer[0],answer[1])}::s\n'.encode()
    text = str(answer)+'\n'
    if case_id == 'B05':
        text += str([(n-1-i)%97 for i in range(n)])+'\n'
    return text.encode()


def validate(case_id, n, result, original=None):
    if json.dumps(result,separators=(',',':')) != json.dumps(expected(case_id,n),separators=(',',':')):
        raise AssertionError(f'{case_id}/{n}: wrong complete result')
    if case_id == 'B05':
        wanted = [(n-1-i)%97 for i in range(n)]
        if original != wanted or Counter(result) != Counter(wanted):
            raise AssertionError('sort changed input or frequency')
    return digest(json.dumps(result,separators=(',',':')).encode())
