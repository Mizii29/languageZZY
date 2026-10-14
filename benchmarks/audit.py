"""Audit completeness and saved evidence without executing timed workloads."""
import argparse
from collections import Counter
import json
from pathlib import Path

from benchmarks.common import digest, source
from benchmarks.run import summarize


def audit(directory):
    directory=Path(directory)
    metadata=json.loads((directory/'environment.json').read_text(encoding='utf-8'))
    environment_id=metadata.pop('environment_id')
    if digest(json.dumps(metadata,sort_keys=True).encode()) != environment_id:
        raise ValueError('environment fingerprint mismatch')
    cases=json.loads((directory/'cases.json').read_text(encoding='utf-8'))['cases']
    cases=[c for c in cases if c['id'] in metadata['selected_cases']]
    rows=[json.loads(line) for line in (directory/'raw.jsonl').read_text(encoding='utf-8').splitlines()]
    if not rows or not cases:
        raise ValueError('empty evidence')
    expected_jobs=set()
    for case in cases:
        sizes=([1,2,10] if case['id']=='B06' else [0,1,2,10,97]) if metadata['verify_only'] else case['sizes']
        for n in sizes:
            for language in ('zzy','python'):
                file=directory/'inputs'/f'{case["id"]}-{n}.{ "zzy" if language=="zzy" else "py"}'
                if file.read_bytes()!=source(case,language,n):
                    raise ValueError('generated input differs: '+str(file))
                for scope in ('cli_total','stages'):
                    expected_jobs.add((case['id'],n,language,scope))
    preflight={}
    counts=Counter()
    indices={}
    for index,row in enumerate(rows):
        if row['order_index']!=index or row['environment_id']!=environment_id:
            raise ValueError('broken order or environment association')
        job=(row['case'],row['n'],row['language'],row['scope'])
        if job not in expected_jobs:
            raise ValueError('unexpected workload')
        if row['phase']=='equivalence':
            if job in preflight:
                raise ValueError('duplicate equivalence check')
            preflight[job]=row['status']=='ok'
        if row['phase'] in {'warmup','sample'}:
            key=(job,row['phase'])
            counts[key]+=1
            indices.setdefault(key,[]).append(row['sample_index'])
        if row['status']=='ok' and not row.get('result_check'):
            raise ValueError('unchecked successful sample')
        if row['status']!='ok' and 'elapsed_ns' in row:
            raise ValueError('failure pretending to be speed sample')
        if row['scope']=='stages' and row['status']=='ok':
            file=directory/'inputs'/f'{row["case"]}-{row["n"]}.{ "zzy" if row["language"]=="zzy" else "py"}'
            if digest(file.read_bytes())!=row['source_sha256']:
                raise ValueError('measured source hash differs')
    if set(preflight)!=expected_jobs:
        raise ValueError('missing equivalence checks')
    eligible=set()
    if not metadata['verify_only']:
        for job in expected_jobs:
            other=(job[0],job[1],'python' if job[2]=='zzy' else 'zzy',job[3])
            if preflight[job] and preflight[other]:
                eligible.add(job)
                for phase,count in [('warmup',3),('sample',15)]:
                    if counts[job,phase]!=count or indices[job,phase]!=list(range(count)):
                        raise ValueError('incomplete or duplicate samples: '+str((job,phase)))
        gated={ (r['case'],r['n'],r['language'],r['scope']) for r in rows if r['phase']=='gate' }
        if gated != expected_jobs-eligible:
            raise ValueError('failed pairs silently omitted')
        if any(job not in eligible for job,phase in counts):
            raise ValueError('measured before paired equivalence')
    summary=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
    if summary!=summarize(rows):
        raise ValueError('summary does not reproduce from raw evidence')
    return dict(evidence_complete=True,records=len(rows),equivalence_jobs=len(preflight),
        measured_jobs=len(eligible),sample_records=sum(r['phase']=='sample' for r in rows),
        failure_records=len(summary['failures']),all_workloads_passed=not summary['failures'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    print(json.dumps(audit(args.directory)))


if __name__=='__main__':main()
