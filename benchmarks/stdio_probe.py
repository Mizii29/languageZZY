"""One-shot stdin correctness/timeout probe, not a statistical speed benchmark."""
import argparse
import json
import os
from pathlib import Path
import random
import subprocess
import time

from benchmarks.common import ROOT, POLICY, digest
from benchmarks.compare import launch
from zzy.process import run_bounded


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparison',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    variants=json.loads((args.comparison/'environment.json').read_text(encoding='utf-8'))['variants']
    args.output.mkdir(parents=True,exist_ok=False)
    path=(args.output/'stdin.zzy').resolve()
    path.write_bytes(b'io.print(len(io.input("")));\n')
    jobs=[(label,size) for label in ('before','after') for size in (4096,65536,1048576)]
    random.Random(20261008).shuffle(jobs)
    rows=[]
    for index,(label,size) in enumerate(jobs):
        runtime=args.comparison/'runtimes'/label
        actual={name:digest((runtime/name).read_bytes()) for name in variants[label]['files']}
        if actual!=variants[label]['files']:
            raise ValueError('runtime snapshot changed')
        stdin=b'x'*size+b'\n'
        cmd=launch(runtime,'cli_total','stdin',size,path)
        row=dict(variant=label,revision=variants[label]['revision'],codepoints=size,
                 stdin_bytes=len(stdin),stdin_sha256=digest(stdin),source_sha256=digest(path.read_bytes()),
                 command=cmd,timeout_seconds=30,repetitions=1,order_seed=20261008,order_index=index,
                 resource_fingerprint=POLICY.fingerprint,not_statistical_performance=True)
        start=time.perf_counter_ns()
        try:
            status,stdout,stderr=run_bounded(cmd,cwd=ROOT,env=os.environ.copy(),timeout=30,stdin=stdin)
            row.update(status='ok' if (status,stdout,stderr)==(0,f'{size}\n'.encode(),b'') else 'failure',
                exit_code=status,stdout=stdout.decode('utf-8',errors='replace'),stderr=stderr.decode('utf-8',errors='replace'))
        except subprocess.TimeoutExpired:
            row.update(status='timeout')
        row['parent_elapsed_ns']=time.perf_counter_ns()-start
        rows.append(row)
        print(label,size,row['status'],flush=True)
        (args.output/'probe.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 1 if any(r['status']!='ok' for r in rows) else 0


if __name__=='__main__':raise SystemExit(main())
