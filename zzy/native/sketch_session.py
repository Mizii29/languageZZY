"""GUI protocol and execution-side dispatch. This module never imports Tk."""
from dataclasses import dataclass, fields, is_dataclass, replace
from queue import Queue, Empty, Full
from threading import Event, RLock
import time

from ..values import Value, NULL, Array
from ..diagnostics import ResourceExceeded, Phase
from . import sketch

QUEUE_LIMIT = 4096
QUEUE_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class Scene:
    width: int
    height: int
    title: str
    background: tuple
    geometries: tuple
    pens: tuple
    layers: tuple
    history_length: int = 0
    playback_position: int = -1
    input_callbacks: tuple = ()


def snapshot(c):
    return Scene(c.width,c.height,c.title,c.background,
        tuple(b.geometry for layer in c.layers if layer.visible for b in c.objects if b.geometry.layer==layer.id),
        tuple((p.name,p.state) for p in c.pens.values()),
        tuple((layer.id,layer.name,layer.visible,layer.locked) for layer in c.layers),len(c.history),-1,tuple(c.callbacks))


def message_size(value):
    if isinstance(value,str):return 4*len(value)
    if isinstance(value,tuple):return 8*len(value)+sum(message_size(v) for v in value)
    if is_dataclass(value):return 32+sum(message_size(getattr(value,f.name)) for f in fields(value))
    if value is None:return 0
    if type(value) in (int,float,bool):return 8
    raise TypeError('GUI messages must contain immutable explicit data')


class Session:
    def __init__(self):
        self.events=Queue(QUEUE_LIMIT);self.renders=Queue(1)
        self.closed=Event();self.failed=Event();self.lock=RLock()
        self.bytes=0;self.failure=None

    def fail(self,key,limit,count):
        with self.lock:
            if self.failure is None:self.failure=(key,limit,count)
            self.failed.set();self.closed.set()

    def send(self,event):
        size=message_size(event)
        with self.lock:
            if self.closed.is_set():return
            if self.bytes+size>QUEUE_BYTES:self.fail('sketch.queue_bytes',QUEUE_BYTES,self.bytes+size);return
            try:self.events.put_nowait((event,size));self.bytes+=size
            except Full:self.fail('sketch.input_queue',QUEUE_LIMIT,QUEUE_LIMIT+1)

    def receive(self,timeout=.04):
        event,size=self.events.get(timeout=timeout)
        with self.lock:self.bytes-=size
        return event

    def refresh(self,scene):
        size=message_size(scene)
        with self.lock:
            try:_,previous=self.renders.get_nowait();self.bytes-=previous
            except Empty:pass
            if self.bytes+size>QUEUE_BYTES:self.fail('sketch.queue_bytes',QUEUE_BYTES,self.bytes+size);return
            self.renders.put_nowait((scene,size));self.bytes+=size

    def take_render(self):
        with self.lock:
            scene,size=self.renders.get_nowait();self.bytes-=size;return scene

    def cleanup(self):
        with self.lock:
            for queue in (self.events,self.renders):
                while True:
                    try:queue.get_nowait()
                    except Empty:break
            self.bytes=0


class SessionClosed(BaseException):pass


class CallbackCancellation:
    def __init__(self,base,session,r,n):self.base,self.session,self.r,self.n=base,session,r,n
    def check(self):
        self.base.check()
        if self.session.failure:
            key,limit,count=self.session.failure
            raise ResourceExceeded(key,limit,count,Phase.EXECUTION,self.r.location(self.n),self.n.token.span)
        if self.session.closed.is_set():raise SessionClosed()
    def cancel(self):self.base.cancel()


class Bridge:
    def __init__(self, error=None):
        self.requests=Queue(1)
        self.error=error
        self.active=None


def tool(r,c,n,event):
    """Internal tools use the same guarded native entries as ZZY calls."""
    _, kind, name, color, width, points, content = event
    def call(op,*args):
        values=[a if isinstance(a,Value) else Value('Bool' if type(a)is bool else 'Int' if type(a)is int else 'Float' if type(a)is float else 'String',a) for a in args]
        return sketch.invoke(r,'sketch.'+op,values,n)
    p=c.pens.get(name)
    if p is None:p=call('pen',c,name)
    call('color',p,call('rgb',*color));call('width',p,width)
    call('jump_to',p,*points[0])
    if kind=='text':call('text',p,content,width*8);return
    if kind=='circle':
        import math
        a,b=points[0],points[-1];radius=math.hypot(b[0]-a[0],b[1]-a[1])
        if radius:call('set_heading',p,0);call('jump_to',p,a[0],a[1]-radius);call('circle',p,radius,360)
        return
    if kind=='rectangle':
        a,b=points[0],points[-1];points=(a,(b[0],a[1]),b,(a[0],b[1]),a)
    elif kind=='line':points=(points[0],points[-1])
    elif kind=='polygon':points=(*points,points[0])
    array=Array(r,n)
    for x,y in points[1:]:
        pair=Array(r,n);pair.push(r.scalar('Float',float(x),n),r,n);pair.push(r.scalar('Float',float(y),n),r,n);array.push(pair,r,n)
    call('polyline',p,array)


def show(r,c,n):
    sketch.guard(r,n,c);sketch.ready(r,n,c)
    from .sketch_history import idle
    from .sketch_events import cleanup
    idle(r,c,n)
    bridge=getattr(r,'gui_bridge',None)
    if bridge is None or bridge.error:
        return r.result(False,r.scalar('String',bridge.error if bridge else 'GUI unavailable: run requires --gui',n),n)
    if bridge.active is not None:r.error(n,'E214','同一上下文不可嵌套show')
    session=Session();bridge.active=session
    replay=None;playing=False;deadline=0.;timers={};selected=None
    def callback(handler,arguments):
        base=r.meter.cancellation
        r.meter.cancellation=CallbackCancellation(base,session,r,n)
        try:return (yield from r.call_value(handler,arguments,replace(n,children=(n,*(n for _ in arguments)))))
        finally:r.meter.cancellation=base
    try:
        session.refresh(snapshot(c));bridge.requests.put_nowait(session)
        while not session.closed.is_set():
            r.meter.cancellation.check()
            now=time.monotonic()
            for identity,(ms,handler,owner) in tuple(c.timers.items()):
                due=timers.setdefault(identity,now+ms/1000)
                if now>=due:
                    timers[identity]=now+ms/1000
                    if replay is not None:replay.close();replay=None;playing=False
                    yield from callback(handler,[])
                    session.refresh(snapshot(c))
            for identity in tuple(timers):
                if identity not in c.timers:del timers[identity]
            timeout=min([.04,*[max(.001,due-time.monotonic()) for due in timers.values()]])
            try:event=session.receive(timeout)
            except Empty:event=None
            if event is not None and event[0]=='replay':
                from .sketch_replay import Replay
                if replay is None:replay=Replay(r,c,n)
                action=event[1]
                if action=='play':playing=True;deadline=time.monotonic()
                elif action=='pause':playing=False
                elif action=='step':playing=False;replay.seek(replay.position+1)
                elif action=='seek':playing=False;replay.seek(event[2])
                session.refresh(replay.scene());continue
            if event is None:
                if replay is not None and playing and time.monotonic()>=deadline:
                    replay.seek(replay.position+1);deadline=time.monotonic()+c.interval_ms/1000
                    session.refresh(replay.scene())
                    if replay.position==len(replay.entries):playing=False
                continue
            if replay is not None:replay.close();replay=None;playing=False
            if event[0]=='callback':
                registered=c.callbacks.get(event[1])
                if registered:
                    args=[r.scalar('String' if isinstance(v,str) else 'Int' if type(v)is int else 'Float',v,n) for v in event[2:]]
                    yield from callback(registered[0],args)
            elif event[0]=='tool':
                sketch.invoke(r,'sketch.begin_group',[c,Value('String',event[1])],n)
                tool(r,c,n,event)
                sketch.invoke(r,'sketch.end_group',[c],n)
            elif event[0]=='history':sketch.invoke(r,'sketch.'+event[1],[c],n)
            elif event[0]=='object':
                action,x,y,dx,dy=event[1:]
                if action=='select':
                    value=sketch.invoke(r,'sketch.pick',[c,Value('Float',x),Value('Float',y)],n)
                    selected=value if value.kind=='Int' else None
                elif selected is not None:
                    args=[c,selected]
                    if action=='translate_object':args.extend((Value('Float',dx),Value('Float',dy)))
                    result=sketch.invoke(r,'sketch.'+action,args,n)
                    if action=='copy_object':selected=result
                    if action=='delete_object':selected=None
            elif event[0]=='add_layer':
                sketch.invoke(r,'sketch.add_layer',[c,Value('String',event[1])],n)
            elif event[0]=='set_layer':
                layer=next((l for l in c.layers if l.id==event[2]),None)
                if layer is None:r.error(n,'E203','排队操作的图层已不在当前文档')
                p=c.pens.get(event[1])
                if p is None:p=sketch.invoke(r,'sketch.pen',[c,Value('String',event[1])],n)
                sketch.invoke(r,'sketch.set_layer',[p,layer],n)
            elif event[0]=='layer':
                layer=next((l for l in c.layers if l.id==event[2]),None)
                if layer is None:r.error(n,'E203','排队操作的图层已不在当前文档')
                op=event[1];value=event[3]
                sketch.invoke(r,'sketch.'+op,[layer,Value('Bool' if type(value)is bool else 'Int' if type(value)is int else 'String',value)],n)
            session.refresh(snapshot(c))
        if session.failure:
            key,limit,count=session.failure
            raise ResourceExceeded(key,limit,count,Phase.EXECUTION,r.location(n),n.token.span)
        r.meter.cancellation.check()
        return r.result(True,NULL,n)
    except SessionClosed:
        # Normal close interrupts a running callback, then resumes after show.
        # Failure may arrive between the cancellation proxy's two flag reads.
        if session.failure:
            key,limit,count=session.failure
            raise ResourceExceeded(key,limit,count,Phase.EXECUTION,r.location(n),n.token.span)
        r.meter.cancellation.check()
        return r.result(True,NULL,n)
    finally:
        if replay is not None:replay.close()
        if c.draft is not None:
            c.draft.pen.state=c.draft.before;c.draft=None
        if c.group is not None:
            if c.group:c.history.append((c.group_label,tuple(c.group)))
            c.group=None;c.group_label=''
        session.closed.set();session.cleanup();bridge.active=None;cleanup(c)
