"""Logical hit testing and whole-object edits (no background-paint eraser)."""
from dataclasses import replace
import math
from ..values import NULL
from .sketch import guard, number, capacity, chord_distance
from .sketch_patterns import leaves, transform, budget, own_geometry

PICK_TOLERANCE = 4.0


def hit(g,x,y):
    for leaf in leaves(g):
        if leaf.kind=='dot' and math.hypot(x-leaf.center[0],y-leaf.center[1])<=leaf.diameter/2+PICK_TOLERANCE:return True
        if leaf.kind=='text':
            theta=math.radians(-leaf.angle);dx,dy=x-leaf.center[0],y-leaf.center[1]
            xx=dx*math.cos(theta)-dy*math.sin(theta);yy=dx*math.sin(theta)+dy*math.cos(theta)
            width=.6*leaf.size*len(leaf.text)
            left={'left':0.,'center':-width/2,'right':-width}[leaf.align]
            if left-PICK_TOLERANCE<=xx<=left+width+PICK_TOLERANCE and abs(yy)<=leaf.size/2+PICK_TOLERANCE:return True
        if leaf.boundary:
            inside=False
            for a,b in zip(leaf.boundary,(*leaf.boundary[1:],leaf.boundary[0])):
                if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
            if inside:return True
        for s in leaf.strokes:
            if any(chord_distance((x,y),a,b)<=max(PICK_TOLERANCE,s.width/2) for a,b in zip(s.points,s.points[1:])):return True
    return False


def invoke(r,op,args,n,c):
    if op=='pick':
        x,y=number(r,n,args[1]),number(r,n,args[2])
        for layer in reversed(c.layers):
            if not layer.visible:continue
            for block in reversed(c.objects):
                r.meter.cancellation.check()
                if block.geometry.layer==layer.id and hit(block.geometry,x,y):return r.scalar('Int',block.geometry.id,n)
        return NULL
    identity=args[1].data
    index=next((i for i,b in enumerate(c.objects) if b.geometry.id==identity),None)
    if index is None:r.error(n,'E204','对象ID不存在')
    block=c.objects[index];g=block.geometry
    layer=next(l for l in c.layers if l.id==g.layer)
    if layer.frozen or layer.locked:r.error(n,'E203','对象图层只读')
    if op=='delete_object':
        c.objects.pop(index);c.segments-=block.segments;return NULL
    if op=='copy_object':
        capacity(r,n,'objects',len(c.objects)+1);capacity(r,n,'path_segments',c.segments+block.segments)
        created=own_geometry(r,n,replace(g,id=c.next_id));result=r.scalar('Int',c.next_id,n)
        c.objects.append(created);c.next_id+=1;c.segments+=block.segments;return result
    dx,dy=number(r,n,args[2]),number(r,n,args[3])
    with r.reserve(n,runtime_payload_bytes=budget(g)[0]):
        if g.kind=='group':new=replace(g,children=tuple(transform(r,n,child,dx,dy,1.,0.) for child in g.children))
        else:new=replace(transform(r,n,g,dx,dy,1.,0.),id=g.id,layer=g.layer)
        created=own_geometry(r,n,new)
        r.meter.cancellation.check();c.objects[index]=created
    return NULL
