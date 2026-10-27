"""Real Tk render/seek samples, each isolated in a fresh desktop process."""
import argparse
from datetime import datetime,timezone
import io
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

from .worker import source,peak_memory
from zzy.diagnostics import Phase,ResourceExceeded
from zzy.output import Output
from zzy.prepare import prepare
from zzy.resources import ResourceMeter,ResourcePolicy
from zzy.source import Source
from zzy.native.sketch_gui import run_gui


def sample(size,scenario):
    meter=ResourceMeter(ResourcePolicy(),Phase.FRONTEND)
    text=source(size,scenario,'zzy')+'sketch.show(c);'
    program=prepare(Source.from_bytes(Path('<render-benchmark.zzy>'),text.encode()),meter)
    output=Output(io.StringIO(),io.StringIO(),meter)
    result=dict(size=size,scenario=scenario,platform=platform.platform(),stages={})
    def probe(view,thread):
        real=view.render;start=0.;mode='first_render';expected_position=None
        deadline=time.monotonic()+90;first_items=None;original_scene=None
        result['tk_patchlevel']=view.root.tk.call('info','patchlevel')
        def render(scene):
            nonlocal start,original_scene
            if mode=='first_render' and not start:start=time.perf_counter();original_scene=scene
            real(scene)
        view.render=render
        def poll():
            nonlocal start,mode,first_items,expected_position
            if time.monotonic()>deadline:raise TimeoutError('render phase deadline')
            if (not start or not view.area.winfo_ismapped() or view.area.winfo_width()<=1 or view.area.winfo_height()<=1
                    or not view.render_complete or expected_position is not None and view.scene.playback_position!=expected_position):
                view.window.after(4,poll);return
            result['stages'][mode]=dict(status='ok',seconds=time.perf_counter()-start,items=view.item_count,viewport=[view.area.winfo_width(),view.area.winfo_height()])
            if mode=='first_render':
                first_items=view.area.find_withtag('object:1')
                mode='unchanged_render';start=time.perf_counter();view.render(view.scene)
            elif mode=='unchanged_render':
                assert view.area.find_withtag('object:1')==first_items, result['stages']
                mode='seek_render';expected_position=view.scene.history_length//2
                start=time.perf_counter();view.session.send(('replay','seek',expected_position))
            else:view.close();return
            view.window.after(4,poll)
        view.window.after(4,poll)
    started=time.perf_counter()
    try:
        run_gui(program,output,probe=probe)
        if not result.get('tk_patchlevel') or set(result['stages'])!={'first_render','unchanged_render','seek_render'}:
            raise RuntimeError('real GUI benchmark did not complete all render stages')
        result['status']='ok'
    except ResourceExceeded as error:result.update(status='resource_failure',key=error.key,limit=error.limit,requested=error.requested)
    result['generation_window_and_cleanup_seconds']=time.perf_counter()-started
    result['peak_process_working_set_bytes']=peak_memory()
    assert all(meter.used(k)==0 for k in ('runtime_objects','runtime_slots','runtime_payload_bytes'))
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--size',type=int);parser.add_argument('--scenario',choices=('single','batch','multi'));parser.add_argument('--all',action='store_true');parser.add_argument('--repeats',type=int,default=3);parser.add_argument('--output',type=Path,default=Path('benchmarks/sketch/results/render.json'));args=parser.parse_args()
    if args.repeats<1:parser.error('repeats must be positive')
    if not args.all:
        if args.size is None or args.scenario is None:parser.error('size and scenario required')
        print(json.dumps(sample(args.size,args.scenario),ensure_ascii=False));return 0
    report=dict(started=datetime.now(timezone.utc).isoformat(),repeats=args.repeats,
                runtime_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('zzy').rglob('*.py')},samples=[])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    for repeat in range(args.repeats):
        for scenario in ('single','batch','multi'):
            for size in (1000,10000,100000):
                command=[sys.executable,'-X','utf8','-m','benchmarks.sketch.render','--size',str(size),'--scenario',scenario]
                started=time.perf_counter();entry=dict(repeat=repeat,size=size,scenario=scenario,command=command)
                try:
                    result=subprocess.run(command,capture_output=True,timeout=180)
                    entry.update(seconds=time.perf_counter()-started,exit_code=result.returncode,stdout=result.stdout.decode('utf-8',errors='replace'),stderr=result.stderr.decode('utf-8',errors='replace'))
                    if result.returncode==0 and not result.stderr:entry['measurement']=json.loads(entry['stdout']);entry['status']=entry['measurement']['status']
                    else:entry['status']='process_failure'
                except subprocess.TimeoutExpired:entry.update(seconds=time.perf_counter()-started,status='timeout')
                report['samples'].append(entry)
                args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                print(f'render repeat={repeat} {scenario} {size}: {entry["status"]} {entry["seconds"]:.3f}s',flush=True)
    report['summary']=[]
    for scenario in ('single','batch','multi'):
        for size in (1000,10000,100000):
            selected=[s for s in report['samples'] if (s['scenario'],s['size'])==(scenario,size)]
            summary=dict(scenario=scenario,size=size,statuses={status:sum(s['status']==status for s in selected) for status in {s['status'] for s in selected}},stages={})
            for stage in ('first_render','unchanged_render','seek_render'):
                values=[s['measurement']['stages'][stage]['seconds'] for s in selected if stage in s.get('measurement',{}).get('stages',{})]
                if values:summary['stages'][stage]=dict(n=len(values),median=statistics.median(values),stdev=statistics.stdev(values) if len(values)>1 else None,min=min(values),max=max(values))
            report['summary'].append(summary)
    report['finished']=datetime.now(timezone.utc).isoformat()
    report['driver_passed']=len(report['samples'])==args.repeats*9 and all(s['status'] in {'ok','resource_failure'} for s in report['samples'])
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 0 if report['driver_passed'] else 1


if __name__=='__main__':raise SystemExit(main())
