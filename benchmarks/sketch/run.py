"""Save every paired sample, including failures; no success-only timing report."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

from .worker import source

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--repeats',type=int,default=3);parser.add_argument('--output',type=Path,default=ROOT/'benchmarks/sketch/results/baseline.json');args=parser.parse_args()
    if args.repeats<1:parser.error('repeats must be positive')
    programs=ROOT/'benchmarks/sketch/programs';programs.mkdir(exist_ok=True)
    paths={}
    for scenario in ('single','batch','multi'):
        for size in (1000,10000,100000):
            file=programs/f'{scenario}-{size}.zzy';file.write_text(source(size,scenario,'zzy')+'\n',encoding='utf-8');paths[scenario,size]=file
    report=dict(started=datetime.now(timezone.utc).isoformat(),repeats=args.repeats,
        git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*paths.values(),Path(__file__).with_name('worker.py')]},samples=[])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    def save():args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def execute(command,kind,repeat,scenario,size,language):
        started=time.perf_counter()
        sample=dict(kind=kind,repeat=repeat,scenario=scenario,size=size,language=language,command=command,cwd=str(ROOT))
        try:
            result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=180)
            sample.update(seconds=time.perf_counter()-started,exit_code=result.returncode,
                          stdout=result.stdout.decode('utf-8',errors='replace'),stderr=result.stderr.decode('utf-8',errors='replace'))
            if result.returncode!=0:sample['status']='process_failure'
            elif kind=='cli' and language=='zzy':sample['status']='ok' if result.stdout==b'ready\ndone\n' and not result.stderr else 'output_failure'
            else:
                sample['measurement']=json.loads(sample['stdout'])
                sample['status']='ok' if 'result' in sample['measurement'] and not result.stderr else 'generation_failure'
        except subprocess.TimeoutExpired as error:
            sample.update(status='timeout',seconds=time.perf_counter()-started,stdout=(error.stdout or b'').decode('utf-8',errors='replace'),stderr=(error.stderr or b'').decode('utf-8',errors='replace'))
        report['samples'].append(sample);save()
        print(f'{kind} repeat={repeat} {scenario} {size} {language}: {sample["status"]} {sample["seconds"]:.3f}s',flush=True)
    for repeat in range(args.repeats):
        for scenario in ('single','batch','multi'):
            for size in (1000,10000,100000):
                for language in ('zzy','python') if repeat%2==0 else ('python','zzy'):
                    base=[sys.executable,'-X','utf8','-m','benchmarks.sketch.worker','--size',str(size),'--scenario',scenario,'--language',language]
                    execute(base,'phases',repeat,scenario,size,language)
                    cli=[sys.executable,'-X','utf8','-m','zzy','run',str(paths[scenario,size])] if language=='zzy' else [*base,'--generation-only']
                    execute(cli,'cli',repeat,scenario,size,language)
    groups={}
    for sample in report['samples']:
        key=(sample['kind'],sample['scenario'],sample['size'],sample['language'])
        groups.setdefault(key,[]).append(sample)
    summary=[]
    for key,samples in groups.items():
        entry=dict(zip(('kind','scenario','size','language'),key));entry['statuses']={status:sum(s['status']==status for s in samples) for status in {s['status'] for s in samples}}
        phases={'process_wall':[s['seconds'] for s in samples if s['status']=='ok']}
        if key[0]=='phases':
            names={name for s in samples for name in s.get('measurement',{}).get('stages',{})}
            entry['stage_failures']={name:[s['measurement']['stages'][name] for s in samples if name in s.get('measurement',{}).get('stages',{}) and s['measurement']['stages'][name]['status']!='ok'] for name in names}
            phases.update({name:[s['measurement']['stages'][name]['seconds'] for s in samples if name in s.get('measurement',{}).get('stages',{}) and s['measurement']['stages'][name]['status']=='ok'] for name in names})
        entry['statistics']={name:dict(n=len(values),median=statistics.median(values),mean=statistics.mean(values),stdev=statistics.stdev(values) if len(values)>1 else None,min=min(values),max=max(values)) for name,values in phases.items() if values}
        summary.append(entry)
    report['summary']=summary;report['finished']=datetime.now(timezone.utc).isoformat()
    # Verify paired fixed answers, not merely successful process exit codes.
    pairs={}
    for sample in report['samples']:
        if sample['kind']=='phases' and sample['status']=='ok':pairs.setdefault((sample['repeat'],sample['scenario'],sample['size']),{})[sample['language']]=sample['measurement']['result']
    report['equivalent_pairs']=sum(pair.get('zzy')==pair.get('python') and len(pair)==2 for pair in pairs.values())
    report['expected_pairs']=args.repeats*9
    report['driver_passed']=len(report['samples'])==args.repeats*36 and all(s['status']=='ok' for s in report['samples']) and report['equivalent_pairs']==report['expected_pairs']
    save()
    return 0 if report['driver_passed'] else 1


if __name__=='__main__':raise SystemExit(main())
