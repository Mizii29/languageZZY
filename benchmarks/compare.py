"""Interleave two committed ZZY runtimes using identical task bytes and launcher."""
import argparse
import json
from pathlib import Path
import random
import re
import subprocess
import sys
from unittest.mock import patch

from benchmarks.common import ROOT, POLICY, digest, load_manifest, source
from benchmarks.run import collect, environment, git, summarize


def snapshot(revision, directory):
    if not re.fullmatch('[0-9a-fA-F]{7,40}',revision):
        raise ValueError('use a concrete Git commit hash')
    revision=git('rev-parse','--verify',revision+'^{commit}')
    files=git('ls-tree','-r','--name-only',revision,'--','zzy').splitlines()
    if not files or 'zzy/interpreter.py' not in files:
        raise ValueError('runtime absent from revision')
    hashes={}
    for name in files:
        target=directory/name
        if not target.resolve().is_relative_to(directory.resolve()):
            raise ValueError('unsafe Git tree path')
        target.parent.mkdir(parents=True,exist_ok=True)
        data=subprocess.check_output(['git','show',revision+':'+name],cwd=ROOT)
        target.write_bytes(data)
        hashes[name]=digest(data)
    return dict(revision=revision,files=hashes)


def launch(runtime, scope, case_id, n, path):
    # -I removes ambient PYTHONPATH. Both revisions use this exact launcher;
    # the snapshot takes precedence over the workspace's zzy package.
    prefix="import sys,runpy; sys.path[:0]=[sys.argv.pop(1),sys.argv.pop(1)]; "
    if scope=='cli_total':
        code=prefix+"sys.argv[0]='zzy'; runpy.run_module('zzy',run_name='__main__')"
        tail=['run',str(path),'--diagnostic-format','json']
    else:
        code=prefix+"sys.argv[0]='benchmarks.worker'; runpy.run_module('benchmarks.worker',run_name='__main__')"
        tail=['zzy',case_id,str(n),str(path),'--batch','1']
    return [sys.executable,'-I','-X','utf8','-c',code,str(runtime.resolve()),str(ROOT),*tail]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',required=True)
    parser.add_argument('--after',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cases',nargs='+',default=['B01','B04'])
    parser.add_argument('--n',type=int,default=10000)
    args=parser.parse_args()
    cases=[c for c in load_manifest()['cases'] if c['id'] in args.cases]
    if not cases or {c['id'] for c in cases}!=set(args.cases):
        raise ValueError('empty/unknown case selection')
    args.output.mkdir(parents=True,exist_ok=False)
    variants={label:snapshot(revision,args.output/'runtimes'/label)
              for label,revision in [('before',args.before),('after',args.after)]}
    # Source-level invariant plus identical host/options proves both policies
    # are the same; reject changes rather than pretending policy differences
    # are optimization gains.
    if variants['before']['files']['zzy/resources.py']!=variants['after']['files']['zzy/resources.py']:
        raise ValueError('resource implementation differs; separate experiment required')
    for label in variants:
        policy_command=[sys.executable,'-I','-X','utf8','-c',
            'import sys; sys.path.insert(0,sys.argv[1]); from zzy.resources import ResourcePolicy; print(ResourcePolicy().canonical_json)',
            str((args.output/'runtimes'/label).resolve())]
        actual=json.loads(subprocess.check_output(policy_command,cwd=ROOT,timeout=30))
        if actual!=POLICY.effective_record():
            raise ValueError('effective runtime policy differs')
    metadata=environment()
    metadata.update(variants=variants,cases=args.cases,n=args.n,order_seed=20261008,
        warmups=3,samples=15,batch=1,timeout_seconds=30,
        launcher='both versions use the same isolated runpy CLI/worker wrapper',
        benchmark_driver_hashes={str(p.relative_to(ROOT)):digest(p.read_bytes())
                               for p in sorted((ROOT/'benchmarks').glob('*.py'))})
    metadata['environment_id']=digest(json.dumps(metadata,sort_keys=True).encode())
    (args.output/'environment.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (args.output/'tracked.diff').write_text(git('diff','HEAD','--'),encoding='utf-8')
    inputs=args.output/'inputs'
    inputs.mkdir()
    for case in cases:
        (inputs/f'{case["id"]}-{args.n}.zzy').write_bytes(source(case,'zzy',args.n))
    jobs=[(case['id'],label,scope) for case in cases for label in variants for scope in ('cli_total','stages')]
    rng=random.Random(20261008)
    rows=[]
    with (args.output/'raw.jsonl').open('w',encoding='utf-8') as stream:
        for phase,count in [('equivalence',1),('warmup',3),('sample',15)]:
            for index in range(count):
                rng.shuffle(jobs)
                for case_id,label,scope in jobs:
                    path=(inputs/f'{case_id}-{args.n}.zzy').resolve()
                    cmd=launch(args.output/'runtimes'/label,scope,case_id,args.n,path)
                    # Only substitute command construction, outside collect's
                    # timer. Capture/result checking is the baseline runner.
                    with patch('benchmarks.run.command',return_value=cmd):
                        row=collect('zzy',scope,case_id,args.n,path)
                    row.update(language=label,revision=variants[label]['revision'],phase=phase,
                               sample_index=index,order_index=len(rows),environment_id=metadata['environment_id'])
                    rows.append(row)
                    stream.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
                    stream.flush()
                print(f'{phase} {index+1}/{count}: {len(jobs)} jobs',flush=True)
            if phase=='equivalence' and any(r['status']!='ok' for r in rows):
                break
    report=summarize(rows)
    report['sampling_complete']=len(rows)==len(jobs)*19
    report['paired_resources_unchanged']=True
    (args.output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if not report['sampling_complete'] or report['failures']:
        return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
