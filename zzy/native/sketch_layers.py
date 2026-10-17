"""Layer and text operations, always on the owning execution thread."""
from dataclasses import replace
from ..values import Array, Value, NULL, boolean
from .sketch import Layer, capacity, guard, number, prepare_block


def invoke(r, op, args, n, c, p):
    h = args[0]
    if op == 'layer_info':
        definition = r.field(r.lookup('sketch',n).value,'LayerInfo',n)
        result = Array(r,n)
        for z, layer in enumerate(c.layers):
            fields = dict(name=r.scalar('String',layer.name,n),visible=boolean(layer.visible),
                locked=boolean(layer.locked),count=r.scalar('Int',sum(b.geometry.layer==layer.id for b in c.objects),n),z=r.scalar('Int',z,n))
            item=Value('Shape',(definition,fields),r.reserve(n,runtime_objects=1,runtime_slots=5))
            item.frozen=True
            result.push(item,r,n)
        return result
    if op in {'add_layer','rename_layer'}:
        name = args[1].data
        if not name or any(layer.name==name and layer is not h for layer in c.layers):
            r.error(n,'E208','图层名必须非空且唯一')
        if op == 'add_layer':
            capacity(r,n,'layers',len(c.layers)+1)
            layer=Layer(c,r,n,name,c.next_layer)
            c.layers.append(layer);c.next_layer+=1
            return layer
        owner=r.reserve(n,runtime_payload_bytes=4*len(name))
        h.owners.append(owner);h.name=name
    elif op == 'set_layer':
        if p.frozen or c.frozen:r.error(n,'E203','画笔或画布只读')
        layer=args[1];other=guard(r,n,layer)
        if other is not c:r.error(n,'E203','图层不属于画笔画布')
        p.layer=layer
    elif op in {'layer_visible','lock_layer'}:
        setattr(h,'visible' if op=='layer_visible' else 'locked',args[1].data)
    elif op == 'move_layer':
        index=args[1].data
        if not 0<=index<len(c.layers):r.error(n,'E204','图层位置越界')
        c.layers.remove(h);c.layers.insert(index,h)
    elif op == 'font':
        owner=r.reserve(n,runtime_payload_bytes=4*len(args[1].data))
        p.owners.append(owner);p.state=replace(p.state,font=args[1].data)
    elif op == 'text_align':
        if args[1].data not in {'left','center','right'}:r.error(n,'E208','文字对齐必须为left/center/right')
        p.state=replace(p.state,align=args[1].data)
    elif op == 'text':
        size=number(r,n,args[2],'style_size',True)
        block=prepare_block(r,n,c,kind='text',center=p.state.position,fill=p.state.color,
            layer=p.layer.id,text=args[1].data,font=p.state.font,align=p.state.align,size=size)
        r.meter.cancellation.check()
        c.objects.append(block);c.segments+=1;c.next_id+=1
    else:raise AssertionError(op)
    return NULL
