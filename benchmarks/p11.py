"""P11 serial interleaved revision measurements, independent answers and immutable snapshots."""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import tempfile
from time import perf_counter_ns

from benchmarks.common import ROOT, POLICY, load_manifest, source, expected, expected_stdout
from benchmarks.run import environment
from zzy.process import run_bounded


def workloads():
    jobs=[]
    for case in load_manifest()['cases']:
        sizes=(10,100,1000) if case['id']=='B04' else (100,)
        for n in sizes:
            jobs.append(dict(case=case['id'],n=n,source=source(case,'zzy',n).decode(),answer=expected(case['id'],n),stdout=expected_stdout(case['id'],n).decode(),python=source(case,'python',n).decode()))
    for n in (10,100,1000):
        code=f'(zno)n:={n};(zno)a:=[];(for)i(in)0..<n{{array.push(a,i);}}(addnew)bench(){{(zno)s:=array.stats(a);(return)[s.count,s.sum,s.min,s.max];}}io.print(bench());'
        answer=[n,n*(n-1)//2,0,n-1]
        reference=f'from benchmarks.p11_reference import CheckedStats\nchecked=CheckedStats(list(range({n})))\nprint(checked.stats())\nchecked.close()\n'
        jobs.append(dict(case='S01',n=n,source=code,answer=answer,stdout=str(answer)+'\n',python=reference))
    for case,mod,take,keep in [('Q01',7,100,1),('Q02',100,3,2),('Q03',1,0,1)]:
        n=100
        code=f'(shape)T{{id:(Int);key:(Int);}}(zno)a:=[];(for)i(in)0..<{n}{{array.push(a,T::{{id:i,key:({n}-i)%{mod}}});}}(addnew)bench(){{(return)a ?>{{(keep):@.id%{keep}==0;(order):@.key(desc);(take):{take};(yield):@.id;}};}}io.print(bench());'
        answer=[i for k in range(mod-1,-1,-1) for i in range(n) if i%keep==0 and (n-i)%mod==k][:take]
        jobs.append(dict(case=case,n=n,source=code,answer=answer,stdout=str(answer)+'\n'))
    jobs.append(dict(case='K01',n=100,source='(zno)c:=sketch.canvas(200,200,"bench");(zno)p:=sketch.pen(c,"p");(addnew)bench(){(for)i(in)0..<100{sketch.forward(p,1);}(return)sketch.position(p).x==100;}io.print(bench());',answer=True,stdout='true\n'))
    for case in ('D01','D02','R01'):
        jobs.append(dict(case=case,n=1000,source='io.print(1);',answer=None,stdout=None))
    return jobs


def snapshot(ref, destination):
    if ref=='WORKTREE':
        files={p.relative_to(ROOT).as_posix():p.read_bytes() for p in (ROOT/'zzy').rglob('*.py')}
    else:
        ref=subprocess.check_output(['git','rev-parse',ref+'^{commit}'],cwd=ROOT,text=True).strip()
        names=subprocess.check_output(['git','ls-tree','-r','--name-only',ref,'--','zzy'],cwd=ROOT,text=True).splitlines()
        files={name:subprocess.check_output(['git','show',ref+':'+name],cwd=ROOT) for name in names if name.endswith('.py')}
    for name,raw in files.items():
        path=destination/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    return dict(revision=ref,source_sha256={name:hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest() for name,raw in sorted(files.items())})


def statistics_rows(rows):
    groups=defaultdict(list)
    for row in rows:
        if row['phase']!='sample' or row['status']!='ok':continue
        times=row.get('timings',{'cli_total_ns':row['wall_ns']})
        for scope,value in times.items():groups[row['variant'],row['case'],row['n'],scope].append(value)
    result=[]
    for (variant,case,n,scope),values in sorted(groups.items()):
        median=statistics.median(values)
        result.append(dict(variant=variant,case=case,n=n,scope=scope,count=len(values),min=min(values),max=max(values),median=median,MAD=statistics.median(abs(v-median) for v in values)))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',default='WORKTREE');parser.add_argument('--after')
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--cases',nargs='+')
    parser.add_argument('--verify-only',action='store_true');parser.add_argument('--profile',action='store_true')
    args=parser.parse_args();jobs=[j for j in workloads() if not args.cases or j['case'] in args.cases]
    if not jobs or args.cases and set(args.cases)!={j['case'] for j in jobs}:parser.error('empty/unknown case selection')
    args.output.mkdir(parents=True,exist_ok=False)
    meta=environment();meta.update(driver_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),ROOT/'benchmarks/p11_worker.py',ROOT/'benchmarks/p11_reference.py')},warmups=3,samples=15,
                                  scope='P11 small/medium fixed workloads; no P07 historical timing reuse; fresh process/state per sample; stages instrumented separately from real CLI; no profiler during timing')
    rows=[]
    with tempfile.TemporaryDirectory(prefix='zzy p11 snapshots ') as directory:
        variants={}
        for name,ref in [('before',args.before),('after',args.after)]:
            if ref is not None:
                folder=Path(directory)/name
                meta.setdefault('variants',{})[name]=snapshot(ref,folder);variants[name]=folder
        (args.output/'environment.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (args.output/'manifest.json').write_text(json.dumps(jobs,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        with (args.output/'raw.jsonl').open('w',encoding='utf-8') as log:
            def collect(job,variant,scope,phase,index,profile=None):
                folder=variants[variant];path=folder/(job['case']+str(job['n'])+'.zzy');path.write_text(job['source'],encoding='utf-8')
                if scope=='cli':cmd=[sys.executable,'-X','utf8','-m','zzy','run',str(path)]
                else:
                    cmd=[sys.executable,'-X','utf8','-c','import sys;sys.path.insert(0,sys.argv.pop(1));from benchmarks.p11_worker import main;raise SystemExit(main())',str(folder),job['case'],str(job['n']),str(path),json.dumps(job['answer'])]
                    if profile:cmd+=['--profile',str(profile.resolve())]
                row=dict(variant=variant,case=job['case'],n=job['n'],scope=scope,phase=phase,index=index,command=cmd)
                start=perf_counter_ns()
                try:
                    code,out,err=run_bounded(cmd,cwd=folder if scope=='cli' else ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT),PYTHONUTF8='1'),timeout=30)
                    row.update(wall_ns=perf_counter_ns()-start,exit_code=code)
                    if scope=='cli':row.update(status='ok' if code==0 and not err and out.decode()==job['stdout'] else 'failure',stdout=out.decode(),stderr=err.decode())
                    else:
                        row.update(json.loads(out));assert code==0 and not err and row['status']=='ok',(code,err,row)
                except BaseException as error:row.update(status='failure',error=type(error).__name__+': '+str(error))
                rows.append(row);log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush();return row['status']=='ok'
            eligible=[]
            for job in jobs:
                scopes=['stages']+(['cli'] if job['stdout'] is not None else [])
                ok=True
                # Independent Python work/answers for the unchanged B01-B09 sources.
                if 'python' in job:
                    p=Path(directory)/'reference.py';p.write_text(job['python'],encoding='utf-8')
                    code,out,err=run_bounded([sys.executable,'-X','utf8',str(p)],cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT)),timeout=30)
                    ok=code==0 and not err and out.decode().replace('\r\n','\n')==job['stdout']
                    row=dict(variant='python',case=job['case'],n=job['n'],scope='cli',phase='equivalence',status='ok' if ok else 'failure',stdout=out.decode(),stderr=err.decode())
                    rows.append(row);log.write(json.dumps(row)+'\n');log.flush()
                for variant in variants:
                    for scope in scopes:ok=collect(job,variant,scope,'equivalence',0) and ok
                if ok:eligible.append((job,scopes))
            if args.profile:
                for job,scopes in eligible:
                    if job['case'] in {'B01','B04','B07','D01','R01'}:
                        collect(job,'before','stages','profile',0,args.output/(job['case']+str(job['n'])+'-profile.txt'))
            if not args.verify_only:
                rng=random.Random(1101)
                for phase,count in [('warmup',3),('sample',15)]:
                    for index in range(count):
                        order=list(eligible);rng.shuffle(order)
                        for job,scopes in order:
                            versions=list(variants)
                            if index%2:versions.reverse()
                            for scope in scopes:
                                for variant in versions:collect(job,variant,scope,phase,index)
                        print(phase,index+1,flush=True)
    failures=[r for r in rows if r['status']!='ok']
    summary=dict(passed=not failures and len(eligible)==len(jobs),failures=failures,records=len(rows),statistics=statistics_rows(rows))
    (args.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=summary['passed'],records=len(rows),failures=len(failures))))
    return 0 if summary['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
