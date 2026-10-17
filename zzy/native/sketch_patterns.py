"""Immutable drawings, strict schema and source-checked reusable ZZY libraries."""
from dataclasses import replace
import json
import math
from pathlib import Path
from threading import get_ident

from ..diagnostics import DiagnosticError, Phase, ResourceExceeded
from ..resources import ResourceMeter
from ..source import Source
from ..prepare import prepare
from ..lexer import Lexer
from ..values import Value
from . import files, json_codec
from .sketch import (Handle, Geometry, Stroke, Block, LIMITS, capacity, guard, number,
                     point, prepare_block)
from .sketch_history import idle


class Drawing(Handle):
    def __init__(self,blocks,r,n):
        super().__init__('Drawing',r,n,slots=len(blocks)+1)
        self.blocks=tuple(blocks);self.frozen=True

    def freeze_native(self,r,n):
        owned(r,n,self)


def owned(r,n,d):
    if d.context is not r.native_context or d.thread!=get_ident() or not r.native_active:
        r.error(n,'E203','Drawing不属于当前活动执行上下文')


def leaves(geometry):
    return geometry.children if geometry.kind=='group' else (geometry,)


def geometry_record(g):
    def strokes():return [dict(points=s.points,color=s.color,width=s.width) for s in g.strokes]
    if g.kind=='path':return dict(type='path',strokes=strokes())
    if g.kind=='fill':return dict(type='fill',strokes=strokes(),boundary=g.boundary,fill=g.fill)
    if g.kind=='dot':return dict(type='dot',center=g.center,diameter=g.diameter,fill=g.fill)
    if g.kind=='text':return dict(type='text',center=g.center,text=g.text,font=g.font,align=g.align,size=g.size,angle=g.angle,fill=g.fill)
    if g.kind=='group':return dict(type='group',children=[geometry_record(child) for child in g.children])
    raise AssertionError(g.kind)


def bounded_text(r,n,parts):
    chunks=[];owners=[];length=size=0
    try:
        for part in parts:
            r.meter.cancellation.check()
            length+=len(part);size+=json_codec.utf8_size(r,part,n)
            r.check('text_codepoints',length,n);r.check('io_payload_bytes',size,n)
            owners.append(r.reserve(n,runtime_slots=2,runtime_payload_bytes=4*len(part)))
            chunks.append(part)
        with r.reserve(n,runtime_payload_bytes=4*length):return r.scalar('String',''.join(chunks),n)
    finally:
        for owner in owners:owner.release()


def encode(r,n,record):
    def string_parts(text):
        yield '"'
        escapes={'"':'\\"','\\':'\\\\','\b':'\\b','\f':'\\f','\n':'\\n','\r':'\\r','\t':'\\t'}
        for char in text:
            yield escapes.get(char,'\\u%04x'%ord(char) if ord(char)<32 else char)
        yield '"'
    def visit(value,depth=0):
        r.meter.cancellation.check()
        if isinstance(value,str):yield from string_parts(value)
        elif value is None:yield 'null'
        elif type(value)is bool:yield 'true' if value else 'false'
        elif type(value)is int:yield r.text_value(Value('Int',value),n).data
        elif type(value)is float:
            if not math.isfinite(value):raise ValueError('nonfinite JSON')
            yield repr(value)
        else:
            r.check('value_depth',depth+1,n)
            if type(value)is dict:
                yield '{'
                for i,(key,item) in enumerate(value.items()):
                    if i:yield ','
                    yield from string_parts(key);yield ':';yield from visit(item,depth+1)
                yield '}'
            elif type(value) in (tuple,list):
                yield '['
                for i,item in enumerate(value):
                    if i:yield ','
                    yield from visit(item,depth+1)
                yield ']'
            else:raise ValueError('unsupported JSON record')
    def buffered():
        chunks=[];size=0
        for part in visit(record):
            r.meter.cancellation.check()
            chunks.append(part);size+=len(part)
            if size>=4096:yield ''.join(chunks);chunks=[];size=0
        if chunks:yield ''.join(chunks)
    with r.reserve(n,runtime_payload_bytes=32768,runtime_slots=4096):
        return bounded_text(r,n,buffered())


class Decoded:
    def __init__(self,r,n,text):
        self.owners=[]
        value=json_codec.parse(r,text,n)
        def convert(v):
            r.meter.cancellation.check()
            if v.kind=='Map':
                self.owners.append(r.reserve(n,runtime_slots=len(v.data)*2))
                return {k:convert(child) for k,child in v.data.items()}
            if v.kind=='Array':
                self.owners.append(r.reserve(n,runtime_slots=len(v.data)))
                return [convert(child) for child in v.data]
            return v.data
        try:self.data=convert(value)
        except BaseException:
            self.close();raise

    def close(self):
        for owner in self.owners:owner.release()
        self.owners.clear()

    def __del__(self):
        self.close()


def fields(data,keys):
    if type(data)is not dict or set(data)!=set(keys.split()):raise ValueError('unexpected schema fields')


def scalar(value,limit,positive=False):
    if type(value) not in (int,float) or not -limit<=value<=limit or positive and value<=0:
        raise ValueError('invalid bounded finite number')
    return float(value)


def rgb(value):
    if type(value)is not list or len(value)!=3 or any(type(v)is not int or not 0<=v<=255 for v in value):raise ValueError('invalid RGB')
    return tuple(value)


def xy(value):
    if type(value)is not list or len(value)!=2:raise ValueError('invalid point')
    return tuple(scalar(v,LIMITS['coordinate_abs']) for v in value)


def decode_geometry(r,n,data,identity=0,layer=0,child=False):
    if type(data)is not dict:raise ValueError('geometry must be object')
    kind=data.get('type')
    if kind in {'path','fill'}:
        fields(data,'type strokes'+(' boundary fill' if kind=='fill' else ''))
        if type(data['strokes'])is not list or not data['strokes']:raise ValueError('path requires strokes')
        strokes=[];segments=0
        for s in data['strokes']:
            r.meter.cancellation.check();fields(s,'points color width')
            if type(s['points'])is not list or len(s['points'])<2:raise ValueError('stroke requires two points')
            segments+=len(s['points'])-1;capacity(r,n,'path_segments',segments)
            strokes.append(Stroke(tuple(xy(p) for p in s['points']),rgb(s['color']),scalar(s['width'],LIMITS['style_size'],True)))
        boundary=();fill=None
        if kind=='fill':
            if type(data['boundary'])is not list:raise ValueError('invalid fill boundary')
            boundary=tuple(xy(p) for p in data['boundary']);fill=rgb(data['fill'])
            if len(set(boundary))<3:raise ValueError('fill needs three distinct vertices')
            if any(a.points[-1]!=b.points[0] for a,b in zip(strokes,strokes[1:])):raise ValueError('disconnected fill strokes')
            if boundary!=tuple(p for i,s in enumerate(strokes) for p in s.points[1 if i else 0:]):raise ValueError('inconsistent fill boundary')
        return Geometry(identity,kind,tuple(strokes),boundary,fill,layer=layer)
    if kind=='dot':
        fields(data,'type center diameter fill')
        center=xy(data['center']);diameter=scalar(data['diameter'],LIMITS['style_size'],True)
        if any(abs(v)+diameter/2>LIMITS['coordinate_abs'] for v in center):raise ValueError('dot bounds')
        return Geometry(identity,kind,fill=rgb(data['fill']),center=center,diameter=diameter,layer=layer)
    if kind=='text':
        fields(data,'type center text font align size angle fill')
        if type(data['text'])is not str or type(data['font'])is not str or data['align'] not in ('left','center','right'):raise ValueError('invalid text style')
        return Geometry(identity,kind,fill=rgb(data['fill']),center=xy(data['center']),layer=layer,text=data['text'],font=data['font'],align=data['align'],size=scalar(data['size'],LIMITS['style_size'],True),angle=scalar(data['angle'],LIMITS['angle_abs']))
    if kind=='group' and not child:
        fields(data,'type children')
        if type(data['children'])is not list:raise ValueError('invalid group')
        capacity(r,n,'objects',len(data['children']))
        return Geometry(identity,kind,layer=layer,children=tuple(decode_geometry(r,n,g,layer=layer,child=True) for g in data['children']))
    raise ValueError('unknown or nested geometry type')


def budget(g):
    size=128;slots=4;segments=0
    for leaf in leaves(g):
        points=sum(len(s.points) for s in leaf.strokes)+len(leaf.boundary)
        size+=128+48*len(leaf.strokes)+16*points+4*(len(leaf.text)+len(leaf.font))
        slots+=4+len(leaf.strokes)+points
        segments+=sum(len(s.points)-1 for s in leaf.strokes)+(1 if leaf.kind in {'dot','text'} else 0)
    return size,slots,segments


def own_geometry(r,n,g):
    size,slots,segments=budget(g)
    return Block(g,segments,r.reserve(n,runtime_objects=1,runtime_slots=slots,runtime_payload_bytes=size))


def transform(r,n,g,x,y,scale,angle):
    theta=math.radians(angle);a,b=math.cos(theta)*scale,math.sin(theta)*scale
    def pt(p):return point(r,n,x+a*p[0]-b*p[1],y+b*p[0]+a*p[1])
    def style(value):return number(r,n,Value('Float',value*scale),'style_size',True)
    strokes=[]
    for s in g.strokes:
        r.meter.cancellation.check()
        strokes.append(Stroke(tuple(pt(p) for p in s.points),s.color,style(s.width)))
    center=pt(g.center) if g.center is not None else None
    diameter=style(g.diameter) if g.kind=='dot' else g.diameter
    if g.kind=='dot':point(r,n,center[0]-diameter/2,center[1]-diameter/2);point(r,n,center[0]+diameter/2,center[1]+diameter/2)
    return replace(g,id=0,layer=0,strokes=tuple(strokes),boundary=tuple(pt(p) for p in g.boundary),center=center,
                   diameter=diameter,size=style(g.size) if g.kind=='text' else g.size,angle=(g.angle+angle)%360)


def quote(text):
    parts=['"'];index=0
    escapes={'"':'[OoO]q','\n':'[OoO]n','\r':'[OoO]r','\t':'[OoO]t'}
    while index<len(text):
        if text.startswith('[OoO]',index):parts.append('[OoO][OoO]');index+=5
        else:parts.append(escapes.get(text[index],text[index]));index+=1
    parts.append('"');return ''.join(parts)


def invoke(r,op,args,n):
    decoded=None
    try:
        if op=='drawing_from_json':
            decoded=Decoded(r,n,args[0].data);data=decoded.data
            fields(data,'schema_version kind objects')
            if type(data['schema_version'])is not int or data['schema_version']!=1 or data['kind']!='zzy-drawing':raise ValueError('unsupported drawing schema')
            if type(data['objects'])is not list:raise ValueError('objects must be array')
            capacity(r,n,'objects',len(data['objects']))
            blocks=[];segments=0
            for item in data['objects']:
                # Parsed JSON already owns bounded input; reserve decode scratch.
                with r.reserve(n,runtime_payload_bytes=4*len(args[0].data)):
                    g=decode_geometry(r,n,item)
                    block=own_geometry(r,n,g)
                segments+=block.segments;capacity(r,n,'path_segments',segments);blocks.append(block)
            return r.result(True,Drawing(blocks,r,n),n)
        if op=='capture':
            c=args[0];guard(r,n,c);idle(r,c,n)
            return Drawing([b for layer in c.layers if layer.visible for b in c.objects if b.geometry.layer==layer.id],r,n)
        if op=='stamp':
            c,d=args[:2];guard(r,n,c,write=True);owned(r,n,d)
            if c.layer.locked or c.layer.frozen:r.error(n,'E203','默认图层只读')
            x,y=number(r,n,args[2]),number(r,n,args[3])
            scale=number(r,n,args[4],positive=True);angle=number(r,n,args[5],'angle_abs')
            size=sum(budget(b.geometry)[0] for b in d.blocks)
            with r.reserve(n,runtime_payload_bytes=size):
                children=tuple(transform(r,n,g,x,y,scale,angle) for b in d.blocks for g in leaves(b.geometry))
                block=prepare_block(r,n,c,kind='group',children=children)
                result=r.scalar('Int',c.next_id,n)
                r.meter.cancellation.check()
                c.objects.append(block);c.next_id+=1;c.segments+=block.segments
            return result
        d=args[0];owned(r,n,d)
        size=sum(budget(b.geometry)[0] for b in d.blocks)
        with r.reserve(n,runtime_payload_bytes=size):
            encoded=encode(r,n,dict(schema_version=1,kind='zzy-drawing',objects=[geometry_record(b.geometry) for b in d.blocks]))
        if op=='drawing_text':return r.result(True,encoded,n)
        if op=='save_function':
            if not d.blocks:raise ValueError('画布很干净，但暂时没有作品可以出道')
            name=args[2].data
            meter=ResourceMeter(r.meter.policy,Phase.FRONTEND,r.meter.cancellation)
            source=Source.from_bytes(Path('<sketch-name>'),name.encode('utf-8'))
            tokens=Lexer(source,meter).scan()
            if len(tokens)!=2 or tokens[0].kind!='IDENT' or tokens[0].lexeme!=name:raise ValueError('invalid function name')
            private='__sketch_data' if name!='__sketch_data' else '__sketch_payload'
            # Escape before the real front end; Lazy makes import/check inert.
            with r.reserve(n,runtime_payload_bytes=32*len(encoded.data)+2048):
                text=f'(zno){private}:=(zzz)(sketch.drawing_from_json({quote(encoded.data)}));\n(addnew) {name}(canvas,x,y,scale,angle) -> (Result) {{\n(zno)d:=wake({private})?;\n(return) (^_^)(sketch.stamp(canvas,d,x,y,scale,angle));\n}}\n'
                raw=text.encode('utf-8')
                r.check('source_file_bytes',len(raw),n)
                try:prepare(Source.from_bytes(Path('<sketch-export.zzy>'),raw),meter)
                except ResourceExceeded as error:
                    raise ResourceExceeded(error.key,error.limit,error.requested,Phase.EXECUTION,r.location(n),n.token.span) from None
                value=r.scalar('String',text,n)
            return files.invoke(r,'io.write_atomic',[args[1],value],n)
        raise AssertionError(op)
    except (ValueError,UnicodeError,json_codec.InvalidJSON,DiagnosticError) as error:
        if isinstance(error,DiagnosticError) and error.diagnostic.code not in {'E101','E102','E103','E301','E302','E304'}:raise
        return r.result(False,r.scalar('String','sketch format/export: '+str(error),n),n)

    finally:
        if decoded is not None:decoded.close()
