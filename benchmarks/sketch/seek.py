"""Targeted post-audit Replay remeasurement, with fixed answers and failures."""
import argparse
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from unittest.mock import patch

from .worker import source,peak_memory
from zzy.diagnostics import Phase,ResourceExceeded
from zzy.interpreter import Interpreter
from zzy.output import Output
from zzy.prepare import prepare
from zzy.resources import ResourceMeter,ResourcePolicy
from zzy.source import Source
from zzy.native.sketch_metadata import ABI
from zzy.native.sketch_replay import Replay


def sample(size,scenario):
    meter=ResourceMeter(ResourcePolicy(),Phase.FRONTEND)
    text=source(size,scenario,'zzy')
    program=prepare(Source.from_bytes(Path('<seek-remeasurement.zzy>'),text.encode()),meter)
    runtime=Interpreter(program,Output(io.StringIO(),io.StringIO(),meter))
    report=dict(size=size,scenario=scenario,abi=ABI,policy=meter.policy.effective_record(),fingerprint=meter.policy.fingerprint)
    def mark(value):
        if value!='done\n':return
        c=runtime.bindings[id(program.root.children[0])].value
        expected=size//min(size,10000) if scenario=='batch' else size
        assert (c.segments,len(c.objects))==(size,expected)
        original=tuple(c.objects);states={k:p.state for k,p in c.pens.items()}
        started=time.perf_counter();replay=None
        try:
            replay=Replay(runtime,c,program.root)
            replay.seek(len(c.history)//2);replay.seek(len(c.history));replay.seek(0)
            assert not replay.scene().geometries
            report.update(status='ok',seconds=time.perf_counter()-started,checkpoints=len(replay.checkpoints))
        except ResourceExceeded as error:
            report.update(status='resource_failure',seconds=time.perf_counter()-started,key=error.key,limit=error.limit,requested=error.requested)
        finally:
            if replay is not None:replay.close()
        assert tuple(c.objects)==original and {k:p.state for k,p in c.pens.items()}==states
    with patch.object(runtime.output,'write',mark):runtime.run()
    assert all(meter.used(k)==0 for k in ('runtime_objects','runtime_slots','runtime_payload_bytes'))
    report['peak_process_working_set_bytes']=peak_memory()
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--size',type=int);parser.add_argument('--scenario',choices=('single','batch','multi'));parser.add_argument('--all',action='store_true');parser.add_argument('--repeats',type=int,default=3);parser.add_argument('--output',type=Path,default=Path('benchmarks/sketch/results/seek-final.json'));args=parser.parse_args()
    if not args.all:
        if args.size is None or args.scenario is None:parser.error('size and scenario required')
        print(json.dumps(sample(args.size,args.scenario),ensure_ascii=False));return 0
    if args.repeats<1:parser.error('repeats must be positive')
    report=dict(started=datetime.now(timezone.utc).isoformat(),repeats=args.repeats,
                runtime_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('zzy').rglob('*.py')},samples=[])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    def save():args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for repeat in range(args.repeats):
        for scenario in ('single','batch','multi'):
            for size in (1000,10000,100000):
                command=[sys.executable,'-X','utf8','-m','benchmarks.sketch.seek','--size',str(size),'--scenario',scenario]
                s=dict(repeat=repeat,size=size,scenario=scenario,command=command)
                try:
                    result=subprocess.run(command,capture_output=True,timeout=180)
                    s.update(exit_code=result.returncode,stdout=result.stdout.decode('utf-8',errors='replace'),stderr=result.stderr.decode('utf-8',errors='replace'))
                    if result.returncode==0 and not result.stderr:s['measurement']=json.loads(s['stdout']);s['status']=s['measurement']['status']
                    else:s['status']='process_failure'
                except subprocess.TimeoutExpired:s['status']='timeout'
                report['samples'].append(s);save()
                print(f'seek repeat={repeat} {scenario} {size}: {s["status"]}',flush=True)
    report['summary']=[]
    for scenario in ('single','batch','multi'):
        for size in (1000,10000,100000):
            selected=[s for s in report['samples'] if (s['scenario'],s['size'])==(scenario,size)]
            values=[s['measurement']['seconds'] for s in selected if s['status']=='ok']
            stats=dict(n=len(values),median=statistics.median(values),stdev=statistics.stdev(values) if len(values)>1 else None) if values else None
            report['summary'].append(dict(scenario=scenario,size=size,statistics=stats,statuses={status:sum(s['status']==status for s in selected) for status in {s['status'] for s in selected}}))
    report['finished']=datetime.now(timezone.utc).isoformat()
    report['driver_passed']=len(report['samples'])==args.repeats*9 and all(s['status'] in {'ok','resource_failure'} for s in report['samples'])
    save();return 0 if report['driver_passed'] else 1


if __name__=='__main__':raise SystemExit(main())
