"""Strict JSON conversion with checked depth, integers, containers and buffers."""
import json
import math
import re

from ..values import Array, Map, Value, NULL, boolean
from ..quantities import join_text

NUMBER = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?')

class InvalidJSON(ValueError):
    pass


def utf8_size(runtime, text, node):
    size = 0
    for index, char in enumerate(text):
        if index % 4096 == 0: runtime.meter.cancellation.check()
        n = ord(char)
        if 0xD800 <= n <= 0xDFFF: raise InvalidJSON('孤立代理码点')
        size += 1 if n < 128 else 2 if n < 2048 else 3 if n < 65536 else 4
    return size


def decimal_integer(runtime, text, node):
    # Bounded accumulation also handles small bit limits without rejecting a
    # conservative decimal-to-binary upper bound or allocating a huge int first.
    value=runtime.scalar('Int',0,node)
    for char in text:
        runtime.meter.cancellation.check()
        if char in '+-':continue
        value=runtime.integer_operation('MULTIPLY',value.data,10,node)
        value=runtime.integer_operation('PLUS',value.data,ord(char)-48,node)
    if text.startswith('-'):
        owner=runtime.reserve(node,runtime_payload_bytes=(value.data.bit_length()+7)//8)
        value=Value('Int',-value.data,owner)
    return value


class Reader:
    def __init__(self, runtime, text, node):
        self.runtime, self.text, self.node, self.index = runtime, text, node, 0

    def spaces(self):
        while self.index < len(self.text) and self.text[self.index] in ' \t\r\n': self.index += 1

    def take(self, char):
        self.spaces()
        if self.text[self.index:self.index+1] == char:
            self.index += 1
            return True
        return False

    def string(self):
        self.spaces()
        start = self.index
        if not self.take('"'): raise InvalidJSON('需要 JSON String')
        count = 0
        while self.index < len(self.text):
            if self.index % 4096 == 0:self.runtime.meter.cancellation.check()
            char = self.text[self.index]; self.index += 1
            if char == '"':
                # Count decoded code points before allocating. Escaped strings
                # must not be rejected by a worst-case decoded-size estimate.
                length = self.index - start
                owner = self.runtime.reserve(self.node, runtime_payload_bytes=4 * count)
                try:
                    with self.runtime.reserve(self.node, runtime_payload_bytes=4 * length):
                        decoded = json.loads(self.text[start:self.index])
                    return Value('String', decoded, owner)
                except BaseException:
                    owner.release()
                    raise
            if ord(char) < 32: raise InvalidJSON('JSON String 含控制字符')
            if char == '\\':
                if self.index >= len(self.text):raise InvalidJSON('未结束的 JSON 转义')
                escape=self.text[self.index];self.index+=1
                if escape=='u':
                    code=self.hex4()
                    if 0xD800<=code<=0xDBFF:
                        if self.text[self.index:self.index+2]!='\\u':raise InvalidJSON('孤立代理码点')
                        self.index+=2
                        if not 0xDC00<=self.hex4()<=0xDFFF:raise InvalidJSON('孤立代理码点')
                    elif 0xDC00<=code<=0xDFFF:raise InvalidJSON('孤立代理码点')
                elif escape not in '"\\/bfnrt':raise InvalidJSON('非法 JSON 转义')
            count+=1
            self.runtime.check('text_codepoints',count,self.node)
        raise InvalidJSON('未结束的 JSON String')

    def hex4(self):
        end=self.index+4
        raw=self.text[self.index:end]
        if len(raw)!=4 or any(c not in '0123456789abcdefABCDEF' for c in raw):
            raise InvalidJSON('非法 Unicode 转义')
        self.index=end
        return int(raw,16)

    def value(self, depth=0):
        r, node = self.runtime, self.node
        r.meter.cancellation.check(); self.spaces()
        char = self.text[self.index:self.index+1]
        if char == '"': return self.string()
        if char in ('[','{'):
            r.check('value_depth',depth+1,node)
            self.index += 1
            result = Array(r,node) if char=='[' else Map(r,node)
            end = ']' if char=='[' else '}'
            if self.take(end): return result
            while True:
                r.check('container_items',len(result.data)+1,node)
                if char=='{':
                    key=self.string()
                    if key.data in result.data: raise InvalidJSON('JSON 重复键')
                    if not self.take(':'): raise InvalidJSON('需要冒号')
                    result.set(key,self.value(depth+1),r,node)
                else: result.push(self.value(depth+1),r,node)
                if self.take(end): return result
                if not self.take(','): raise InvalidJSON('需要逗号或容器结尾')
        for word, value in (('true',boolean(True)),('false',boolean(False)),('null',NULL)):
            if self.text.startswith(word,self.index):
                self.index += len(word); return value
        match=NUMBER.match(self.text,self.index)
        if match is None: raise InvalidJSON('非法 JSON 值')
        start,self.index=self.index,match.end()
        with r.reserve(node,runtime_payload_bytes=4*(self.index-start)):
            raw=self.text[start:self.index]
            r.check('numeric_digits',sum(c.isdigit() for c in raw),node)
            if any(c in raw for c in '.eE'):
                owner=r.reserve(node,runtime_payload_bytes=8)
                try:
                    number=float(raw)
                    if not math.isfinite(number):raise InvalidJSON('JSON Float 必须有限')
                    return Value('Float',number,owner)
                except BaseException:
                    owner.release()
                    raise
            digits=len(raw)-(raw[0]=='-')
            if digits>r.meter.policy.decimal_digits:
                r.check('integer_bits',r.meter.policy.limits['integer_bits']+1,node)
            return decimal_integer(r,raw,node)



def parse(runtime, text, node):
    runtime.check('io_payload_bytes',utf8_size(runtime,text,node),node)
    reader=Reader(runtime,text,node)
    result=reader.value();reader.spaces()
    if reader.index!=len(text):raise InvalidJSON('JSON 尾部有多余数据')
    return result


def stringify(runtime, value, node):
    parts, owners, active = [], [], set()
    length=byte_count=0
    def append(text):
        nonlocal length,byte_count
        length+=len(text);byte_count+=utf8_size(runtime,text,node)
        runtime.check('text_codepoints',length,node)
        runtime.check('io_payload_bytes',byte_count,node)
        owners.append(runtime.reserve(node,runtime_payload_bytes=4*len(text),runtime_slots=1))
        parts.append(text)
    def string(text):
        utf8_size(runtime,text,node)
        size=2+sum(2 if c in '\\"\b\f\n\r\t' else 6 if ord(c)<32 else 1 for c in text)
        runtime.check('text_codepoints',size,node)
        with runtime.reserve(node,runtime_payload_bytes=4*size):
            append(json.dumps(text,ensure_ascii=False,separators=(',',':')))
    def visit(item,depth):
        runtime.meter.cancellation.check()
        if item.kind=='String':string(item.data)
        elif item.kind=='Int':append(runtime.text_value(item,node).data)
        elif item.kind in {'Float','Bool','Null'}:append(runtime.scalar_text(item,node))
        elif item.kind in {'Array','Map','Shape'}:
            runtime.check('value_depth',depth+1,node)
            if id(item) in active:raise InvalidJSON('循环引用不能序列化')
            active.add(id(item))
            try:
                if item.kind=='Array':
                    append('[')
                    for i,child in enumerate(item.data):
                        if i:append(',')
                        visit(child,depth+1)
                    append(']')
                else:
                    fields=item.data if item.kind=='Map' else item.data[1]
                    append('{')
                    for i,(key,child) in enumerate(fields.items()):
                        if i:append(',')
                        string(key);append(':');visit(child,depth+1)
                    append('}')
            finally:active.remove(id(item))
        else:raise InvalidJSON(f'{item.kind} 不能序列化')
    try:
        visit(value,0)
        return join_text(runtime,parts,node)
    finally:
        for owner in owners:owner.release()
