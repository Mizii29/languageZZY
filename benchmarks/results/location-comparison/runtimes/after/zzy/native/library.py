"""Registered native execution with the same value and callback boundaries."""
from dataclasses import replace
from pathlib import Path
from ..source import Source
from ..tokens import Token
import re

from ..ast_nodes import Node
from ..values import Array, Map, Value, NULL, boolean
from .. import quantities
from . import files, json_codec


class Library:
    def validate_native(self, function, args, node):
        for index,(value,kinds) in enumerate(zip(args,function.argument_types)):
            if kinds and value.kind not in kinds:
                if function.name in {'core.len','core.str'}:
                    self.error(node,'E201',function.name+' 不支持此类型')
                self.typecheck('|'.join(kinds),value,node.children[index+1])

    def stats_definition(self,node):
        source=Source.from_bytes(Path("<native array.Stats>"),b"array.Stats count sum min max")
        def token(name):
            start=source.text.index(name)
            return Token("IDENT",source,start,start+len(name))
        fields=tuple(Node('field',token(name),data=kind)
                     for name,kind in (('count','Int'),('sum','Int'),('min',None),('max',None)))
        declaration=Node('shape',token('array.Stats'),fields)
        return Value('Definition',(declaration,{f.token.lexeme:f.data for f in fields}),
                     self.reserve(node,runtime_objects=1,runtime_slots=4))

    def native_call(self,name,args,node):
        if name in {'array.map','array.filter'}:
            values,callback=args
            result=Array(self,node)
            call=replace(node,children=(node.children[2],node.children[1]))
            values.active+=1
            try:
                for item in values.data:
                    self.meter.cancellation.check()
                    with self.reserve(node,runtime_slots=1):
                        mapped=yield from self.call_value(callback,[item],call)
                    if name=='array.filter':
                        self.typecheck('Bool',mapped,node.children[2])
                        if mapped.data:result.push(item,self,node)
                    else:result.push(mapped,self,node)
                return result
            finally:values.active-=1
        if name in {'core.len','core.str','core.range','io.print','io.input','array.copy','array.push','array.pop'}:
            return self.call(name,args,node)
        if name.startswith('io.'):return files.invoke(self,name,args,node)
        if name.startswith('unit.'):return self.unit_call(name,args,node)
        if name.startswith('data.'):return self.data_call(name,args,node)
        if name.startswith('text.'):return self.text_call(name,args,node)
        if name=='math.abs':
            value=args[0]
            size=(value.data.bit_length()+7)//8 if value.kind=='Int' else 8
            owner=self.reserve(node,runtime_payload_bytes=size)
            return Value(value.kind,abs(value.data),owner)
        values=args[0]
        if name in {'array.sum','array.stats'}:
            total=self.scalar('Int',0,node);minimum=maximum=NULL
            for item in values.data:
                self.meter.cancellation.check()
                self.typecheck('Int',item,node.children[1])
                total=self.integer_operation('PLUS',total.data,item.data,node)
                if minimum is NULL or item.data<minimum.data:minimum=item
                if maximum is NULL or item.data>maximum.data:maximum=item
            if name=='array.sum':return total
            count=self.scalar('Int',len(values.data),node)
            namespace=self.lookup('array',node).value
            definition=self.field(namespace,'Stats',node)
            return Value('Shape',(definition,dict(count=count,sum=total,min=minimum,max=maximum)),
                         self.reserve(node,runtime_objects=1,runtime_slots=5))
        if name=='array.sorted':
            kind=values.data[0].kind if values.data else None
            if kind not in {None,'Int','String'}:self.error(node,'E201','sorted 仅接受统一 Int/String')
            for item in values.data:
                if item.kind!=kind:self.error(node,'E201','sorted 元素类型不一致')
            with self.reserve(node,runtime_slots=3*len(values.data)):
                def key(item):
                    self.meter.cancellation.check()
                    return item.data
                ordered=sorted(values.data,key=key)
                result=Array(self,node)
                for item in ordered:result.push(item,self,node)
                return result
        raise AssertionError('registered function has no implementation: '+name)

    def unit_call(self,name,args,node):
        number,label=args
        if label.data not in quantities.UNITS:self.error(node.children[2],'E306','未知单位')
        scale,dimensions=quantities.UNITS[label.data]
        unit=quantities.value(self,scale,dimensions,node)
        if name=='unit.make':return quantities.calculate(self,'MULTIPLY',number,unit,node)
        if number.data[1]!=dimensions:self.error(node,'E213','目标单位量纲不匹配')
        converted=quantities.calculate(self,'DIVIDE',number,unit,node)
        fraction=converted.data[0]
        numerator=self.text_value(Value('Int',fraction.numerator),node)
        denominator=self.text_value(Value('Int',fraction.denominator),node) if fraction.denominator!=1 else None
        return quantities.join_text(self,(numerator.data,'/' if denominator else '',
                  denominator.data if denominator else '', '::',label.data),node)

    def text_call(self,name,args,node):
        if name=='text.trim':
            text=args[0].data;start=0;end=len(text)
            while start<end and text[start].isspace():start+=1
            while end>start and text[end-1].isspace():end-=1
            owner=self.reserve(node,runtime_payload_bytes=4*(end-start))
            return Value('String',text[start:end],owner)
        if name=='text.contains':return boolean(args[1].data in args[0].data)
        if name=='text.safe_int':
            text=args[0].data;start=0;end=len(text)
            while start<end and text[start] in ' \t\r\n':start+=1
            while end>start and text[end-1] in ' \t\r\n':end-=1
            with self.reserve(node,runtime_payload_bytes=4*(end-start)):
                return self.safe_integer(text[start:end],node)
        if name=='text.join':
            values,separator=args
            for item in values.data:self.typecheck('String',item,node.children[1])
            length=sum(len(item.data) for item in values.data)+max(0,len(values.data)-1)*len(separator.data)
            self.check('text_codepoints',length,node)
            with self.reserve(node,runtime_slots=len(values.data)):
                owner=self.reserve(node,runtime_payload_bytes=4*length)
                return Value('String',separator.data.join(item.data for item in values.data),owner)
        if name=='text.replace':
            old,new,value=args
            if not old.data:self.error(node,'E208','替换目标不能为空')
            count=value.data.count(old.data)
            size=len(value.data)+count*(len(new.data)-len(old.data))
            self.check('text_codepoints',size,node)
            owner=self.reserve(node,runtime_payload_bytes=4*size)
            return Value('String',value.data.replace(old.data,new.data),owner)
        if name=='text.split':
            value,separator=args
            if not separator.data:self.error(node,'E208','分隔符不能为空')
            count=value.data.count(separator.data)+1
            self.check('container_items',count,node)
            result=Array(self,node)
            start=0
            while True:
                self.meter.cancellation.check()
                end=value.data.find(separator.data,start)
                stop=len(value.data) if end<0 else end
                owner=self.reserve(node,runtime_payload_bytes=4*(stop-start))
                result.push(Value('String',value.data[start:stop],owner),self,node)
                if end<0:return result
                start=end+len(separator.data)
        raise AssertionError(name)

    def safe_integer(self,text,node):
        digits=sum('0'<=c<='9' for c in text)
        self.check('numeric_digits',digits,node)
        if digits>self.meter.policy.decimal_digits:
            self.check('integer_bits',self.meter.policy.limits['integer_bits']+1,node)
        if not re.fullmatch(r'[+-]?[0-9]+',text):
            return self.result(False,self.scalar('String','invalid integer',node),node)
        return self.result(True,json_codec.decimal_integer(self,text,node),node)

    def data_call(self,name,args,node):
        if name=='data.map':return Map(self,node)
        value=args[0]
        if name=='data.kind':
            kind=value.kind.lower() if value.kind in {'Null','Bool','Int','Float','String','Array','Map'} else 'other'
            return self.scalar('String',kind,node)
        if name=='data.has':return boolean(args[1].data in value.data)
        if name=='data.get':
            if args[1].data not in value.data:self.error(node,'E204','Map 键不存在')
            return value.data[args[1].data]
        if name=='data.set':
            value.set(args[1],args[2],self,node);return NULL
        if name=='data.keys':
            result=Array(self,node)
            for key in value.keys.values():result.push(key,self,node)
            return result
        if name in {'data.parse','data.stringify'}:
            try:
                converted=json_codec.parse(self,value.data,node) if name=='data.parse' else json_codec.stringify(self,value,node)
                return self.result(True,converted,node)
            except json_codec.InvalidJSON as error:
                return self.result(False,self.scalar('String',str(error),node),node)
        raise AssertionError(name)
