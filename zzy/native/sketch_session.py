"""GUI protocol and execution-side dispatch. This module never imports Tk."""
from dataclasses import dataclass
from queue import Queue, Empty, Full
from threading import Event
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


def snapshot(c):
    return Scene(c.width,c.height,c.title,c.background,
        tuple(b.geometry for layer in c.layers if layer.visible for b in c.objects if b.geometry.layer==layer.id),
        tuple((p.name,p.state) for p in c.pens.values()),
        tuple((layer.id,layer.name,layer.visible,layer.locked) for layer in c.layers),len(c.history))


class Session:
    def __init__(self):
        self.events=Queue(QUEUE_LIMIT)
        # Only the latest render is needed; document edits are never coalesced.
        self.renders=Queue(1)
        self.closed=Event()
        self.failed=Event()

    def send(self, event):
        try:self.events.put_nowait(event)
        except Full:self.failed.set();self.closed.set()

    def refresh(self, scene):
        try:self.renders.get_nowait()
        except Empty:pass
        self.renders.put_nowait(scene)


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
    idle(r,c,n)
    bridge=getattr(r,'gui_bridge',None)
    if bridge is None or bridge.error:
        return r.result(False,r.scalar('String',bridge.error if bridge else 'GUI unavailable: run requires --gui',n),n)
    if bridge.active is not None:r.error(n,'E214','同一上下文不可嵌套show')
    session=Session();bridge.active=session
    replay=None;playing=False;deadline=0.
    try:
        session.refresh(snapshot(c));bridge.requests.put_nowait(session)
        while not session.closed.is_set():
            r.meter.cancellation.check()
            try:event=session.events.get(timeout=.04)
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
            if event[0]=='tool':
                sketch.invoke(r,'sketch.begin_group',[c,Value('String',event[1])],n)
                tool(r,c,n,event)
                sketch.invoke(r,'sketch.end_group',[c],n)
            elif event[0]=='history':sketch.invoke(r,'sketch.'+event[1],[c],n)
            session.refresh(snapshot(c))
        if session.failed.is_set():
            raise ResourceExceeded('sketch.input_queue',QUEUE_LIMIT,QUEUE_LIMIT+1,Phase.EXECUTION,r.location(n),n.token.span)
        r.meter.cancellation.check()
        return r.result(True,NULL,n)
    finally:
        if replay is not None:replay.close()
        session.closed.set();bridge.active=None
    yield  # Retain generator protocol for later ZZY callbacks, not a success stub.
