"""Versioned document graph and delta history, validated before publication."""
from dataclasses import asdict, replace

from ..values import Value
from . import files
from .sketch import Canvas, Layer, Pen, PenState, capacity, LIMITS
from .sketch_history import Delta, Label, idle, COMMANDS, BYTES
from .sketch_patterns import (Decoded, fields, rgb, xy, scalar, geometry_record,
                             decode_geometry, own_geometry, budget, encode)


def integer(value,minimum=0,maximum=None):
    if type(value)is not int or value<minimum or maximum is not None and value>maximum:raise ValueError('invalid integer field')
    return value


def string(value,nonempty=False):
    if type(value)is not str or nonempty and not value:raise ValueError('invalid string field')
    return value


def boolean(value):
    if type(value)is not bool:raise ValueError('invalid Boolean field')
    return value


def pen_state(data):
    fields(data,'position heading down color fill width cursor font align')
    heading=scalar(data['heading'],360)
    if not 0<=heading<360 or data['align'] not in ('left','center','right'):raise ValueError('invalid pen direction/alignment')
    return PenState(xy(data['position']),heading,boolean(data['down']),rgb(data['color']),rgb(data['fill']),
        scalar(data['width'],LIMITS['style_size'],True),boolean(data['cursor']),string(data['font']),data['align'])


def collect(c):
    layers={l.id:l for l in c.layers}
    blocks={id(b):b for b in c.objects}
    for p in c.pens.values():layers[p.layer.id]=p.layer
    for _,entry in (*c.history,*c.redo_history):
        for d in entry:
            for _,b in (*d.added,*d.removed):blocks[id(b)]=b
            for obj,key,before,after in d.attrs:
                if isinstance(obj,Layer):layers[obj.id]=obj
                if key=='layer':layers[before.id]=before;layers[after.id]=after
                if key=='layers':
                    for layer in (*before,*after):layers[layer.id]=layer
    return layers,tuple(blocks.values())


def record(c,layers,blocks):
    references={id(b):i for i,b in enumerate(blocks)}
    def target(obj):return 'canvas' if obj is c else 'layer:'+str(obj.id) if isinstance(obj,Layer) else 'pen:'+obj.name
    def value(key,item):
        if key=='state':return asdict(item)
        if key=='layer':return item.id
        if key=='layers':return [l.id for l in item]
        return item
    def history(entries):
        return [dict(label=label,deltas=[dict(attrs=[dict(target=target(obj),key=key,before=value(key,before),after=value(key,after)) for obj,key,before,after in d.attrs],
                     removed=[[i,references[id(b)]] for i,b in d.removed],added=[[i,references[id(b)]] for i,b in d.added]) for d in entry]) for label,entry in entries]
    return dict(schema_version=1,kind='zzy-project',width=c.width,height=c.height,title=c.title,background=c.background,
        next_id=c.next_id,next_layer=c.next_layer,interval_ms=c.interval_ms,
        layers=[dict(id=l.id,name=l.name,visible=l.visible,locked=l.locked) for l in layers.values()],
        layer_order=[l.id for l in c.layers],pens=[dict(name=p.name,layer=p.layer.id,state=asdict(p.state)) for p in c.pens.values()],
        geometry=[dict(id=b.geometry.id,layer=b.geometry.layer,data=geometry_record(b.geometry)) for b in blocks],
        objects=[references[id(b)] for b in c.objects],history=history(c.history),redo=history(c.redo_history))


def load(r,n,data):
    fields(data,'schema_version kind width height title background next_id next_layer interval_ms layers layer_order pens geometry objects history redo')
    if type(data['schema_version'])is not int or data['schema_version']!=1 or data['kind']!='zzy-project':raise ValueError('unsupported project schema')
    width=integer(data['width'],1,LIMITS['canvas_dimension']);height=integer(data['height'],1,LIMITS['canvas_dimension'])
    for key in ('layers','layer_order','pens','geometry','objects','history','redo'):
        if type(data[key])is not list:raise ValueError('project lists required')
    capacity(r,n,'layers',len(data['layers']));capacity(r,n,'pens',len(data['pens']))
    c=Canvas(width,height,string(data['title']),r,n,register=False)
    try:
        c.background=rgb(data['background']);c.next_id=integer(data['next_id'],1)
        c.next_layer=integer(data['next_layer'],1);c.interval_ms=integer(data['interval_ms'],1,86400000)
        layers={};targets={'canvas':c}
        for item in data['layers']:
            fields(item,'id name visible locked')
            identity=integer(item['id'])
            if identity in layers or identity>=c.next_layer:raise ValueError('duplicate layer or bad high water')
            layer=c.layer if identity==0 else Layer(c,r,n,identity=identity)
            layer.name=string(item['name'],True);layer.visible=boolean(item['visible']);layer.locked=boolean(item['locked'])
            layer.owners.append(r.reserve(n,runtime_payload_bytes=4*len(layer.name)))
            layers[identity]=layer;targets['layer:'+str(identity)]=layer
        def layer_order(ids):
            if type(ids)is not list or any(type(i)is not int or i not in layers for i in ids) or len(set(ids))!=len(ids) or 0 not in ids:raise ValueError('invalid layer references')
            return tuple(layers[i] for i in ids)
        c.layers=list(layer_order(data['layer_order']))
        if 0 not in layers:raise ValueError('default layer absent')
        c.layer=layers[0]
        for item in data['pens']:
            fields(item,'name layer state');name=string(item['name'],True)
            if name in c.pens:raise ValueError('duplicate pen name')
            layer_id=integer(item['layer'])
            if layer_id not in layers:raise ValueError('bad pen layer')
            p=Pen(c,name,r,n);p.layer=layers[layer_id];p.state=pen_state(item['state'])
            p.owners.append(r.reserve(n,runtime_payload_bytes=4*len(p.state.font)))
            c.pens[name]=p;targets['pen:'+name]=p
        pool=[]
        for item in data['geometry']:
            r.meter.cancellation.check();fields(item,'id layer data')
            identity=integer(item['id'],1);layer=integer(item['layer'])
            if identity>=c.next_id or layer not in layers:raise ValueError('bad geometry references/high water')
            g=decode_geometry(r,n,item['data'],identity,layer)
            pool.append(own_geometry(r,n,g))
        def ref(index):
            integer(index,0,len(pool)-1)
            return pool[index]
        c.objects=[ref(i) for i in data['objects']];c.segments=sum(b.segments for b in c.objects)
        count=cost=0
        def changes(entries):
            nonlocal count,cost
            result=[]
            for item in entries:
                fields(item,'label deltas');label=string(item['label'])
                label=Label(label,r.reserve(n,runtime_payload_bytes=4*len(label)))
                if type(item['deltas'])is not list or not item['deltas']:raise ValueError('empty or invalid history entry')
                deltas=[]
                for item in item['deltas']:
                    fields(item,'attrs removed added')
                    if any(type(item[k])is not list for k in item):raise ValueError('invalid delta lists')
                    attrs=[];seen=set()
                    for attr in item['attrs']:
                        fields(attr,'target key before after')
                        target=string(attr['target']);key=string(attr['key'])
                        if target not in targets or (target,key) in seen:raise ValueError('invalid/duplicate attribute target')
                        seen.add((target,key));obj=targets[target]
                        allowed={'segments','background','layers'} if obj is c else {'state','layer'} if isinstance(obj,Pen) else {'name','visible','locked'}
                        if key not in allowed:raise ValueError('forbidden history field')
                        def convert(v):
                            if key=='state':return pen_state(v)
                            if key=='layer':
                                integer(v)
                                if v not in layers:raise ValueError('unknown history layer')
                                return layers[v]
                            if key=='layers':return layer_order(v)
                            if key=='segments':return integer(v,0,LIMITS['path_segments'])
                            if key=='background':return rgb(v)
                            if key=='name':return string(v,True)
                            return boolean(v)
                        attrs.append((obj,key,convert(attr['before']),convert(attr['after'])))
                    def pairs(items):
                        result=[];previous=-1
                        for pair in items:
                            if type(pair)is not list or len(pair)!=2:raise ValueError('invalid geometry delta')
                            index=integer(pair[0])
                            if index<=previous:raise ValueError('unordered delta indices')
                            previous=index;result.append((index,ref(pair[1])))
                        return tuple(result)
                    removed,added=pairs(item['removed']),pairs(item['added'])
                    if not attrs and not removed and not added:raise ValueError('empty delta')
                    label_cost=4*len(label) if not deltas else 0
                    size=160+64*len(attrs)+16*(len(removed)+len(added))+label_cost;count+=1;cost+=size
                    if count>COMMANDS or cost>BYTES:
                        from ..diagnostics import ResourceExceeded,Phase
                        raise ResourceExceeded('sketch.history_commands' if count>COMMANDS else 'sketch.history_bytes',COMMANDS if count>COMMANDS else BYTES,count if count>COMMANDS else cost,Phase.EXECUTION,r.location(n),n.token.span)
                    owner=r.reserve(n,runtime_slots=2+4*len(attrs)+len(removed)+len(added),runtime_payload_bytes=size-label_cost)
                    deltas.append(Delta(tuple(attrs),removed,added,size,owner))
                result.append((label,tuple(deltas)))
            return result
        c.history=changes(data['history']);c.redo_history=changes(data['redo']);c.history_count=count;c.history_bytes=cost
        validate_history(r,c,n)
        result=r.result(True,c,n)
        r.native_canvases.add(c)
        return result
    except BaseException:
        c.cleanup();c.pens.clear();c.layers.clear();c.layer.canvas=None
        raise


def validate_history(r,c,n):
    """Walk backwards and forwards, checking each delta's claimed preconditions."""
    # A validator uses an isolated attribute map and object list, not live handles.
    values={};objects=list(c.objects);ids=set();segments=c.segments
    layer_counts={}
    for b in objects:layer_counts[b.geometry.layer]=layer_counts.get(b.geometry.layer,0)+1
    for _,entry in (*c.history,*c.redo_history):
        for d in entry:
            for obj,key,_,_ in d.attrs:values[(id(obj),key)]=tuple(getattr(obj,key)) if key=='layers' else getattr(obj,key)
    def get(obj,key):return values.get((id(obj),key),getattr(obj,key))
    def valid():
        capacity(r,n,'objects',len(objects));capacity(r,n,'path_segments',segments)
        if segments!=get(c,'segments'):raise ValueError('history segment count mismatch')
        layers=get(c,'layers')
        if any(count and identity not in {l.id for l in layers} for identity,count in layer_counts.items()):raise ValueError('geometry on inactive layer')
        if len({get(l,'name') for l in layers})!=len(layers):raise ValueError('duplicate active layer name')
        for p in c.pens.values():
            if get(p,'layer') not in layers:raise ValueError('pen on inactive layer')
    for b in objects:
        if b.geometry.id in ids:raise ValueError('duplicate active object ID')
        ids.add(b.geometry.id)
    valid()
    original=(tuple(objects),dict(values),segments)
    def apply(entry,forward):
        nonlocal segments
        for d in entry if forward else reversed(entry):
            r.meter.cancellation.check()
            for obj,key,before,after in d.attrs:
                expected=before if forward else after;actual=get(obj,key)
                if key=='state':expected=replace(expected,cursor=actual.cursor)
                if actual!=expected:raise ValueError('history before/after mismatch')
            remove,add=(d.removed,d.added) if forward else (d.added,d.removed)
            for index,b in reversed(remove):
                if index>=len(objects) or objects[index] is not b:raise ValueError('history removal mismatch')
                objects.pop(index);ids.remove(b.geometry.id);segments-=b.segments
                layer_counts[b.geometry.layer]-=1
            for index,b in add:
                if index>len(objects) or b.geometry.id in ids:raise ValueError('history addition mismatch')
                objects.insert(index,b);ids.add(b.geometry.id);segments+=b.segments
                layer_counts[b.geometry.layer]=layer_counts.get(b.geometry.layer,0)+1
            for obj,key,before,after in d.attrs:values[(id(obj),key)]=after if forward else before
            valid()
    for _,entry in reversed(c.history):apply(entry,False)
    for _,entry in c.history:apply(entry,True)
    for _,entry in reversed(c.redo_history):apply(entry,True)
    for _,entry in c.redo_history:apply(entry,False)
    if tuple(objects)!=original[0] or segments!=original[2]:raise ValueError('history did not restore current document')


def invoke(r,op,args,n):
    if op=='save_project':
        c=args[0];idle(r,c,n)
        layers,blocks=collect(c)
        size=sum(budget(b.geometry)[0] for b in blocks)+c.history_bytes+1024*(len(layers)+len(c.pens))
        with r.reserve(n,runtime_payload_bytes=size):text=encode(r,n,record(c,layers,blocks))
        return files.invoke(r,'io.write_atomic',[args[1],text],n)
    result=files.invoke(r,'io.read_text',args,n)
    if not result.data[0]:return result
    decoded=None
    try:
        decoded=Decoded(r,n,result.data[1].data)
        with r.reserve(n,runtime_payload_bytes=4*len(result.data[1].data)):
            return load(r,n,decoded.data)
    except ValueError as error:
        return r.result(False,r.scalar('String','sketch project: '+str(error),n),n)

    finally:
        if decoded is not None:decoded.close()
