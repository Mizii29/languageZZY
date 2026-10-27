"""Context-owned callback registration; dispatch only at show boundaries."""
from ..values import NULL, boolean
from .sketch_history import interval
from .sketch import capacity

ARITY={'on_click':3,'on_drag':3,'on_release':3,'on_key':1,'every':0}


def invoke(r,op,args,n,c):
    if op=='cancel_timer':
        timer=c.timers.pop(args[1].data,None)
        if timer is not None:timer[2].release()
        return boolean(timer is not None)
    callback=args[-1]
    if callback.kind!='Function' or len(callback.data.parameters)!=ARITY[op]:r.error(n,'E202','sketch回调固定参数数量不符')
    if op=='every':
        duration=interval(r,n,args[1]);capacity(r,n,'timers',len(c.timers)+1)
        result=r.scalar('Int',c.next_timer,n)
        owner=r.reserve(n,runtime_slots=2,runtime_payload_bytes=32)
        c.timers[c.next_timer]=(duration,callback,owner);c.next_timer+=1
        return result
    owner=r.reserve(n,runtime_slots=2,runtime_payload_bytes=32)
    kind=op.removeprefix('on_')
    old=c.callbacks.get(kind)
    c.callbacks[kind]=(callback,owner)
    if old:old[1].release()
    return NULL


def cleanup(c):
    for _,owner in c.callbacks.values():owner.release()
    for _,_,owner in c.timers.values():owner.release()
    c.callbacks.clear();c.timers.clear()
