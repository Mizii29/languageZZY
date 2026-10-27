"""One fresh process per sample; Python calls the identical generic host API."""
import argparse
from contextlib import nullcontext
import ctypes
import hashlib
import io
import json
from pathlib import Path
import platform
import tempfile
import time
from unittest.mock import patch

from zzy.diagnostics import DiagnosticError, Phase, ResourceExceeded
from zzy.interpreter import Interpreter
from zzy.output import Output
from zzy.prepare import prepare
from zzy.resources import ResourceMeter,ResourcePolicy
from zzy.source import Source
from zzy.values import Array,Value
from zzy.native import sketch,sketch_history
from zzy.native.sketch_metadata import ABI
from zzy.native.sketch_patterns import quote
from zzy.native.sketch_replay import Replay


def peak_memory():
    if platform.system()!='Windows':return None
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),
          *[(name,ctypes.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]]
    value=Counters();value.cb=ctypes.sizeof(value)
    kernel=ctypes.WinDLL('kernel32');psapi=ctypes.WinDLL('psapi')
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(value),value.cb):raise ctypes.WinError()
    return value.PeakWorkingSetSize


def source(size,scenario,language):
    setup='(zno)c:=sketch.canvas(1000,600,"benchmark");(zno)p:=sketch.pen(c,"p");'
    if scenario=='multi':
        setup+='(zno)pens:=[];(for)i(in)range(0,4,1){(zno)q:=sketch.pen(c,"p"+str(i));(zno)l:=sketch.add_layer(c,"l"+str(i));sketch.set_layer(q,l);array.push(pens,q);}'
    setup+='sketch.clear_history(c);io.print("ready");'
    if language=='python':body=''
    elif scenario=='batch':
        chunk=min(size,10000)
        body=f'(for)start(in)range(0,{size},{chunk}){{(zno)points:=[];(for)i(in)range(start,start+{chunk},1){{array.push(points,[i+1,0]);}}sketch.polyline(p,points);}}'
    elif scenario=='multi':body=f'(for)i(in)range(0,{size},1){{sketch.forward(pens[i%4],1);}}'
    else:body=f'(for)i(in)range(0,{size},1){{sketch.forward(p,1);}}'
    return setup+body+'io.print("done");'


def run(size,scenario,language,generation_only=False):
    policy=ResourcePolicy();meter=ResourceMeter(policy,Phase.FRONTEND)
    output=Output(io.StringIO(),io.StringIO(),meter)
    text=source(size,scenario,language)
    started=time.perf_counter();program=prepare(Source.from_bytes(Path('<sketch-benchmark.zzy>'),text.encode()),meter)
    report=dict(size=size,scenario=scenario,language=language,prepare_seconds=time.perf_counter()-started,
        source_sha256=hashlib.sha256(text.encode()).hexdigest(),abi=ABI,policy=policy.effective_record(),fingerprint=policy.fingerprint,
        python=platform.python_version(),platform=platform.platform(),stages={})
    r=Interpreter(program,output);n=program.root;record_seconds=0.;begin=0.
    originals=(sketch_history.Edit.__init__,sketch_history.Edit.finish)
    def instrument(original):
        def measured(*args,**kwargs):
            nonlocal record_seconds
            started=time.perf_counter()
            try:return original(*args,**kwargs)
            finally:record_seconds+=time.perf_counter()-started
        return measured
    def call(op,*args):
        values=[a if isinstance(a,Value) else Value('Int' if type(a)is int else 'Float' if type(a)is float else 'String',a) for a in args]
        return sketch.invoke(r,'sketch.'+op,values,n)
    def stage(name,action):
        started=time.perf_counter()
        try:
            value=action()
            if isinstance(value,Value) and value.kind=='Result' and not value.data[0]:
                report['stages'][name]=dict(status='result_failure',seconds=time.perf_counter()-started,message=value.data[1].data)
                return None
            report['stages'][name]=dict(status='ok',seconds=time.perf_counter()-started)
            return value
        except ResourceExceeded as error:
            report['stages'][name]=dict(status='resource_failure',seconds=time.perf_counter()-started,key=error.key,limit=error.limit,requested=error.requested)
        except DiagnosticError as error:
            report['stages'][name]=dict(status='diagnostic_failure',seconds=time.perf_counter()-started,code=error.diagnostic.code)
    def observe(marker):
        nonlocal begin,record_seconds
        c=r.bindings[id(program.root.children[0])].value;p=c.pens['p']
        if marker=='ready\n':
            begin=time.perf_counter();record_seconds=0.
            if language=='python':
                if scenario=='batch':
                    chunk=min(size,10000)
                    for start in range(0,size,chunk):
                        points=Array(r,n)
                        for i in range(start,start+chunk):
                            pair=Array(r,n);pair.push(r.scalar('Int',i+1,n),r,n);pair.push(r.scalar('Int',0,n),r,n);points.push(pair,r,n)
                        call('polyline',p,points)
                else:
                    for i in range(size):call('forward',c.pens['p'+str(i%4)] if scenario=='multi' else p,1)
            return
        report['stages']['generation']=dict(status='ok',seconds=time.perf_counter()-begin)
        report['stages']['recording_nested']=dict(status='ok',seconds=record_seconds)
        expected_objects=size//min(size,10000) if scenario=='batch' else size
        assert (c.segments,len(c.objects))==(size,expected_objects)
        expected_positions={name:(float(size//4),0.) if scenario=='multi' and name!='p' else (0.,0.) if scenario=='multi' else (float(size),0.) for name in c.pens}
        assert {name:p.state.position for name,p in c.pens.items()}==expected_positions
        cursors={};digest=hashlib.sha256()
        for index,block in enumerate(c.objects):
            g=block.geometry;layer=index%4+1 if scenario=='multi' else 0
            assert (g.id,g.layer,g.kind)==(index+1,layer,'path')
            position=cursors.get(layer,0)
            assert len(g.strokes)==1 and g.strokes[0].color==(0,0,0) and g.strokes[0].width==1.
            for j,(x,y) in enumerate(g.strokes[0].points):assert (x,y)==(position+j,0.)
            cursors[layer]=position+len(g.strokes[0].points)-1
            digest.update(repr((g.id,g.layer,g.strokes[0].points)).encode())
        report['result']=dict(segments=c.segments,objects=len(c.objects),positions=expected_positions,history=len(c.history),next_id=c.next_id,geometry_sha256=digest.hexdigest())
        report['logical_live']={key:r.meter.used(key) for key in ('runtime_objects','runtime_slots','runtime_payload_bytes')}
        if generation_only:return
        def undo():
            while c.history:call('undo',c)
            assert not c.objects
        def redo():
            while c.redo_history:call('redo',c)
            assert len(c.objects)==expected_objects
        stage('undo',undo);stage('redo',redo)
        def seek():
            replay=Replay(r,c,n)
            try:
                replay.seek(len(c.history)//2);replay.seek(len(c.history));replay.seek(0)
                assert not replay.scene().geometries
                return len(replay.checkpoints)
            finally:replay.close()
        checkpoints=stage('seek',seek)
        if checkpoints is not None:report['stages']['seek']['checkpoints']=checkpoints
        svg=stage('svg',lambda:call('svg_text',c))
        if svg:
            import xml.etree.ElementTree as ET
            document=svg.data[1].data
            assert len(ET.fromstring(document).findall('.//{http://www.w3.org/2000/svg}path'))==expected_objects
            report['stages']['svg']['sha256']=hashlib.sha256(document.encode()).hexdigest()
            report['stages']['svg']['bytes']=len(document.encode());del document,svg
        drawing=stage('capture',lambda:call('capture',c))
        if drawing:
            encoded=stage('drawing_encode',lambda:call('drawing_text',drawing))
            if encoded:
                payload=encoded.data[1].data
                # Actual ZZY Lazy on the same decoded Drawing, in a fresh context.
                lazy_source='(zno)d:=(zzz)(sketch.drawing_from_json('+quote(payload)+'));io.print("first");wake(d);io.print("cached");wake(d);io.print("end");'
                lazy_meter=ResourceMeter(policy,Phase.FRONTEND)
                def lazy():
                    raw=lazy_source.encode()
                    lazy_meter.check('source_file_bytes',len(raw));lazy_meter.check('source_total_bytes',len(raw))
                    lazy_program=prepare(Source.from_bytes(Path('<lazy-benchmark.zzy>'),raw),lazy_meter)
                    lazy_output=Output(io.StringIO(),io.StringIO(),lazy_meter);lazy_runtime=Interpreter(lazy_program,lazy_output);clock=0.
                    def mark(value):
                        nonlocal clock
                        now=time.perf_counter()
                        if value!='first\n':
                            cached=lazy_runtime.bindings[id(lazy_program.root.children[0])].value.cached
                            assert cached.data[0],cached.data[1].data
                            report['stages']['first_decode' if value=='cached\n' else 'cached_decode']=dict(status='ok',seconds=now-clock)
                        clock=now
                    with patch.object(lazy_output,'write',mark):lazy_runtime.run()
                stage('lazy_prepare_and_execution',lazy)
                del encoded,payload,lazy_source
            with tempfile.TemporaryDirectory(prefix='ZZY sketch benchmark ') as tmp:
                stage('function_export',lambda:call('save_function',drawing,str(Path(tmp)/'pattern.zzy'),'pattern'))
                stage('project_save',lambda:call('save_project',c,str(Path(tmp)/'drawing.zzysketch')))
    started=time.perf_counter()
    with patch.object(output,'write',observe),patch.object(sketch_history.Edit,'__init__',instrument(originals[0])) if not generation_only else nullcontext(),patch.object(sketch_history.Edit,'finish',instrument(originals[1])) if not generation_only else nullcontext():
        try:r.run()
        except ResourceExceeded as error:report['generation_failure']=dict(key=error.key,limit=error.limit,requested=error.requested)
    report['execution_and_analysis_seconds']=time.perf_counter()-started
    report['peak_process_working_set_bytes']=peak_memory()
    assert all(r.meter.used(k)==0 for k in ('runtime_objects','runtime_slots','runtime_payload_bytes'))
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--size',type=int,required=True);parser.add_argument('--scenario',choices=('single','batch','multi'),required=True);parser.add_argument('--language',choices=('zzy','python'),required=True);parser.add_argument('--generation-only',action='store_true');args=parser.parse_args()
    print(json.dumps(run(args.size,args.scenario,args.language,args.generation_only),ensure_ascii=False))


if __name__=='__main__':main()
