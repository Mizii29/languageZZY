"""Document deltas. Immutable geometry blocks are shared, never copied per edit."""
from dataclasses import dataclass, replace

from ..diagnostics import Phase, ResourceExceeded
from ..values import NULL, boolean

class Label(str):
    def __new__(cls,text,owner):
        value=super().__new__(cls,text);value.owner=owner;return value
    def __del__(self):self.owner.release()


COMMANDS = 100000
BYTES = 64 * 1024 * 1024


@dataclass
class Delta:
    attrs: tuple
    removed: tuple
    added: tuple
    cost: int
    owner: object

    def __del__(self):
        self.owner.release()

    def apply(self,c,forward):
        remove,add=(self.added,self.removed) if not forward else (self.removed,self.added)
        for index,block in reversed(remove):
            assert c.objects[index] is block
            c.objects.pop(index)
        for index,block in add:c.objects.insert(index,block)
        for obj,key,before,after in self.attrs:
            value=after if forward else before
            if key=='state':value=replace(value,cursor=obj.state.cursor)
            setattr(obj,key,list(value) if key=='layers' else value)


def idle(r,c,n):
    if c.group is not None or c.draft is not None:r.error(n,'E214','活动分组或填充期间不可执行此操作')


def operate(r,c,n,op,args):
    if op=='begin_group':
        idle(r,c,n)
        owner=r.reserve(n,runtime_payload_bytes=4*len(args[1].data))
        c.group_label=Label(args[1].data,owner);c.group=[];return NULL
    if op=='end_group':
        if c.group is None or c.draft is not None:r.error(n,'E214','分组未配对或仍有填充草稿')
        if c.group:c.history.append((c.group_label,tuple(c.group)))
        c.group=None;c.group_label='';return NULL
    idle(r,c,n)
    if op=='clear_history':
        c.history.clear();c.redo_history.clear();c.history_bytes=c.history_count=0
        return NULL
    source,target=(c.history,c.redo_history) if op=='undo' else (c.redo_history,c.history)
    if not source:return boolean(False)
    entry=source[-1]
    # Frozen affected handles must not be mutated indirectly through aliases.
    for delta in entry[1]:
        for obj,key,_,_ in delta.attrs:
            if getattr(obj,'frozen',False):r.error(n,'E203','历史操作影响冻结句柄')
        for _,block in (*delta.added,*delta.removed):
            layer=next((l for l in c.layers if l.id==block.geometry.layer),None)
            if layer is not None and (layer.frozen or layer.locked):r.error(n,'E203','历史操作影响只读图层')
    r.meter.cancellation.check()
    for delta in reversed(entry[1]) if op=='undo' else entry[1]:delta.apply(c,op=='redo')
    source.pop();target.append(entry)
    return boolean(True)


class Edit:
    """A private candidate operation becomes visible only after history reserves.

    The synchronous native call has no callback boundary. Allocation failure
    restores its candidate fields/blocks/ID; completed earlier calls stay intact.
    """
    def __init__(self,r,c,n,op,h,args):
        self.r,self.c,self.n,self.op=r,c,n,op
        self.old_id=c.next_id;self.old_layer_id=c.next_layer
        self.draft=c.draft
        self.handle=h;self.owners_start=len(h.owners)
        fields=[(c,'segments')]
        if h.kind=='sketch.Pen':fields.extend(((h,'state'),(h,'layer')))
        if op=='background':fields.append((c,'background'))
        if op in {'add_layer','move_layer'}:fields.append((c,'layers'))
        if op in {'layer_visible','lock_layer','rename_layer'}:fields.extend((h,k) for k in ('visible','locked','name'))
        self.before=[(obj,key,tuple(getattr(obj,key)) if key=='layers' else getattr(obj,key)) for obj,key in fields]
        self.start=len(c.objects)
        self.removed=tuple(enumerate(c.objects)) if op=='clear' else ()
        if op in {'translate_object','delete_object'}:
            self.removed=tuple((i,b) for i,b in enumerate(c.objects) if b.geometry.id==args[1].data)

    def finish(self):
        c=self.c;r=self.r;n=self.n
        added=tuple(enumerate(c.objects[self.start:],self.start)) if self.op!='clear' else ()
        if self.op=='translate_object':added=tuple((i,c.objects[i]) for i,b in self.removed)
        attrs=[]
        for obj,key,before in self.before:
            after=tuple(getattr(obj,key)) if key=='layers' else getattr(obj,key)
            # Fill drafts write pen state privately; commit history spans begin/end.
            if self.op=='end_fill' and key=='state':before=self.draft.before
            if before!=after:attrs.append((obj,key,before,after))
        if not attrs and not self.removed and not added:return
        label_cost=4*len(c.group_label) if c.group is not None and not c.group else 0
        cost=160+64*len(attrs)+16*(len(self.removed)+len(added))+label_cost
        redo_count=sum(len(entry) for _,entry in c.redo_history)
        redo_bytes=sum(d.cost for _,entry in c.redo_history for d in entry)
        try:
            if c.history_count-redo_count+1>COMMANDS:raise ResourceExceeded('sketch.history_commands',COMMANDS,c.history_count+1,Phase.EXECUTION,r.location(n),n.token.span)
            if c.history_bytes-redo_bytes+cost>BYTES:raise ResourceExceeded('sketch.history_bytes',BYTES,c.history_bytes+cost,Phase.EXECUTION,r.location(n),n.token.span)
            owner=r.reserve(n,runtime_slots=2+len(attrs)*4+len(self.removed)+len(added),runtime_payload_bytes=cost-label_cost)
            delta=Delta(tuple(attrs),self.removed,added,cost,owner)
            r.meter.cancellation.check()
        except BaseException:
            if self.op=='clear':c.objects[:]=[b for _,b in self.removed]
            elif self.op in {'translate_object','delete_object'}:
                if self.op=='translate_object':
                    for i,b in self.removed:c.objects[i]=b
                else:
                    for i,b in self.removed:c.objects.insert(i,b)
            else:del c.objects[self.start:]
            for obj,key,before in self.before:setattr(obj,key,list(before) if key=='layers' else before)
            for owner in self.handle.owners[self.owners_start:]:owner.release()
            del self.handle.owners[self.owners_start:]
            c.next_id,c.next_layer,c.draft=self.old_id,self.old_layer_id,self.draft
            raise
        # New editing discards redo and its counters, but IDs remain high water.
        for _,entry in c.redo_history:
            c.history_count-=len(entry);c.history_bytes-=sum(d.cost for d in entry)
        c.redo_history.clear()
        c.history_count+=1;c.history_bytes+=cost
        if c.group is not None:c.group.append(delta)
        else:c.history.append(('',(delta,)))


def interval(r,n,value):
    # Kept in one boundary for both replay and event timers.
    amount,dimensions=value.data
    if dimensions != (0,1):r.error(n,'E201','间隔必须为时间Quantity')
    from fractions import Fraction
    numerator=r.integer_operation("MULTIPLY",amount.numerator,1000,n).data
    milliseconds=Fraction(numerator,amount.denominator)
    result=-(-milliseconds.numerator//milliseconds.denominator)
    if milliseconds<=0 or result>86400000:r.error(n,'E208','时间间隔必须在(0,24h]')
    return result
