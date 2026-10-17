"""Execution-side playback of recorded deltas, never source or callbacks."""
from .sketch_history import idle
from .sketch_session import Scene


class Replay:
    def __init__(self,r,c,n):
        idle(r,c,n)
        self.r,self.c,self.n=r,c,n
        self.entries=tuple(c.history)
        self.position=len(self.entries)
        self.objects=list(c.objects)
        self.values={}
        for _,entry in self.entries:
            for delta in entry:
                for obj,key,_,_ in delta.attrs:
                    self.values[(id(obj),key)]=tuple(c.layers) if obj is c and key=='layers' else getattr(obj,key)
        self.owners=[];self.checkpoints={}
        self.owner=r.reserve(n,runtime_slots=len(self.objects)+2*len(self.values)+len(self.entries),runtime_payload_bytes=16*len(self.values))
        self.seek(0)
        self.checkpoint()
        self.spacing=max(1,(len(self.entries)+6)//7)

    def close(self):
        for owner in self.owners:owner.release()
        self.owners.clear();self.checkpoints.clear()
        if getattr(self,'owner',None):self.owner.release()

    def __del__(self):
        if hasattr(self,'owners'):self.close()

    def apply(self,entry,forward):
        for delta in entry if forward else reversed(entry):
            remove,add=(delta.removed,delta.added) if forward else (delta.added,delta.removed)
            for i,b in reversed(remove):self.objects.pop(i)
            for i,b in add:self.objects.insert(i,b)
            for obj,key,before,after in delta.attrs:self.values[(id(obj),key)]=after if forward else before

    def checkpoint(self):
        if self.position in self.checkpoints or len(self.checkpoints)>=8:return
        size=8*len(self.objects)+32*len(self.values)
        # A bounded acceleration cache; refusal only disables this optional cache.
        if size+sum(cost for _,_,cost in self.checkpoints.values())>16*1024*1024:return
        if self.r.meter.used('runtime_slots')+len(self.objects)+2*len(self.values)>self.r.meter.policy.limits['runtime_slots']:return
        if self.r.meter.used('runtime_payload_bytes')+size>self.r.meter.policy.limits['runtime_payload_bytes']:return
        owner=self.r.reserve(self.n,runtime_slots=len(self.objects)+2*len(self.values),runtime_payload_bytes=size)
        self.owners.append(owner)
        self.checkpoints[self.position]=(tuple(self.objects),dict(self.values),size)

    def seek(self,target):
        target=max(0,min(len(self.entries),target))
        closest=min([self.position,*self.checkpoints],key=lambda p:abs(target-p))
        if closest!=self.position:
            objects,values,_=self.checkpoints[closest]
            self.objects=list(objects);self.values=dict(values);self.position=closest
        while self.position!=target:
            self.r.meter.cancellation.check()
            forward=self.position<target
            index=self.position if forward else self.position-1
            self.apply(self.entries[index][1],forward)
            self.position+=1 if forward else -1
            if hasattr(self,'spacing') and self.position%self.spacing==0:self.checkpoint()

    def get(self,obj,key):
        return self.values.get((id(obj),key),getattr(obj,key))

    def scene(self):
        c=self.c;layers=self.get(c,'layers')
        return Scene(c.width,c.height,c.title,self.get(c,'background'),
            tuple(b.geometry for layer in layers if self.get(layer,'visible') for b in self.objects if b.geometry.layer==layer.id),
            tuple((p.name,self.get(p,'state')) for p in c.pens.values()),
            tuple((l.id,self.get(l,'name'),self.get(l,'visible'),self.get(l,'locked')) for l in layers),len(self.entries),self.position)
