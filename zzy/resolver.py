"""Lexical resolution, local slots and transitive closure capture planning."""

from dataclasses import replace
import math
from types import MappingProxyType

from .quantities import UNITS, literal
from .ast_nodes import Capture, FunctionPlan, Program, Reference, Symbol
from .diagnostics import Diagnostic, DiagnosticError, display_path


BUILTIN_NAMES = frozenset({"io", "array", "text", "math", "data", "unit", "sketch",
                           "len", "str", "range", "wake"})
IMPLEMENTED_NAMES = frozenset({"io", "array", "len", "str", "range", "wake"})


class FunctionContext:
    def __init__(self, node, parent):
        self.node, self.parent = node, parent
        self.locals, self.captures, self.blocks = [], {}, {}


class Resolver:
    def __init__(self, root, meter):
        self.root, self.meter = root, meter
        self.file = display_path(root.token.source.path)
        self.scopes = [{name: name for name in IMPLEMENTED_NAMES}]
        self.integers, self.references, self.annotations = {}, {}, {}
        self.symbols, self.functions = {}, {}
        self.quantities, self.machines = {}, {}
        self.function = None
        self.loops = 0

    def error(self, token, code, message):
        raise DiagnosticError(Diagnostic(message, code, self.file, token.span))

    def lookup(self, token):
        for scope in reversed(self.scopes):
            if token.lexeme in scope:
                symbol = scope[token.lexeme]
                if symbol is not None:
                    return self.reference(symbol, self.function)
                break
        self.error(token, "E302", f"名称 {token.lexeme} 尚未声明、正在初始化或尚未实现")

    def reference(self, symbol, context):
        if isinstance(symbol, str):
            return Reference("global", symbol, symbol)
        info = self.symbols[symbol]
        if context is None:
            return Reference("global", symbol, symbol)
        if symbol == id(context.node) and context.node.kind == "function":
            return Reference("self", 0, symbol)
        if info.owner == id(context.node):
            return Reference("local", info.slot, symbol)
        if symbol not in context.captures:
            source = self.reference(symbol, context.parent)
            context.captures[symbol] = Capture(source, symbol)
            if info.mutable:
                self.symbols[symbol] = replace(info, cell=True)
        index = tuple(context.captures).index(symbol)
        return Reference("capture", index, symbol)

    def declare(self, node, mutable=False, initialized=False):
        name, symbol = node.token.lexeme, id(node)
        if name in self.scopes[-1] or (len(self.scopes) == 1 and name in BUILTIN_NAMES):
            self.error(node.token, "E301", f"名称 {name} 在当前作用域重复声明")
        context = self.function
        slot = len(context.locals) if context else None
        if context:
            context.locals.append(symbol)
        self.symbols[symbol] = Symbol(id(context.node) if context else None, slot, mutable)
        self.scopes[-1][name] = symbol if initialized else None

    def annotation(self, annotation):
        if annotation is None:
            return
        if isinstance(annotation, tuple):
            self.annotations[id(annotation[0])] = (self.lookup(annotation[0]),
                                                  tuple(t.lexeme for t in annotation[1:]))
        else:
            self.annotations[id(annotation)] = annotation.lexeme[1:-1]

    def block(self, node, loop=None, parameters=(), payload=None):
        context = self.function
        self.scopes.append({})
        try:
            for parameter in parameters:
                self.declare(parameter, mutable=True, initialized=True)
            if payload:
                self.declare(payload, initialized=True)
            if loop:
                self.declare(loop, initialized=True)
            for child in node.children:
                self.statement(child)
        finally:
            if context:
                # Clear only this lexical scope; nested scopes own their own slots.
                context.blocks[id(node)] = tuple(self.symbols[symbol].slot
                    for symbol in self.scopes[-1].values()
                    if isinstance(symbol, int) and self.symbols[symbol].owner == id(context.node))
            self.scopes.pop()

    def resolve_function(self, node):
        # Type names belong to the declaration environment, not its parameters.
        for parameter in node.children[:-1]:
            self.annotation(parameter.data)
        if node.kind != "lazy":
            self.annotation(node.data)
        if node.kind == "function":
            self.scopes[-1][node.token.lexeme] = id(node)
        previous, loops = self.function, self.loops
        context = FunctionContext(node, previous)
        self.function, self.loops = context, 0
        try:
            if node.kind == "function":
                self.block(node.children[-1], parameters=node.children[:-1])
            else:
                self.scopes.append({})
                try:
                    for parameter in node.children[:-1]:
                        self.declare(parameter, mutable=True, initialized=True)
                    self.expression(node.children[-1])
                finally:
                    self.scopes.pop()
        finally:
            self.function, self.loops = previous, loops
        self.functions[id(node)] = FunctionPlan(tuple(context.locals), tuple(context.captures.values()),
                                                MappingProxyType(context.blocks))

    def statement(self, node):
        self.meter.cancellation.check()
        if node.kind == "binding":
            self.declare(node, mutable=node.data[0])
            self.annotation(node.data[1])
            self.expression(node.children[0])
            self.scopes[-1][node.token.lexeme] = id(node)
        elif node.kind == "function":
            self.declare(node)
            self.resolve_function(node)
        elif node.kind == "machine":
            if len(self.scopes) != 1:
                self.error(node.token, "E103", "machine 仅允许文件顶层")
            self.declare(node, initialized=True)
            edges, states = {}, set()
            if not node.children:
                self.error(node.token, "E305", "状态机至少需要一条边")
            for edge in node.children:
                start, event, end = edge.data
                if not event or (start, event) in edges:
                    self.error(edge.token, "E305", "空事件或重复转换")
                edges[start, event] = end
                states.update((start, end))
            self.machines[id(node)] = (MappingProxyType(edges), frozenset(states))
        elif node.kind == "spec":
            if len(self.scopes) != 1 or self.function is not None:
                self.error(node.token, "E103", "spec 仅允许文件顶层")
            self.block(node.children[0])
        elif node.kind == "match":
            self.expression(node.children[0])
            patterns, tags, wildcard = [], set(), False
            for arm in node.children[1:]:
                pattern, body = arm.children
                if wildcard:
                    self.error(pattern.token, "E103", "兜底模式必须最后且唯一")
                if pattern.kind == "wildcard":
                    wildcard = True
                elif pattern.kind == "payload_pattern":
                    if pattern.data in tags:
                        self.error(pattern.token, "E103", "重复 Result 标签")
                    tags.add(pattern.data)
                else:
                    self.expression(pattern.children[0])
                    key = self.pattern_key(pattern.children[0])
                    if key in patterns:
                        self.error(pattern.token, "E103", "重复相等常量模式")
                    patterns.append(key)
                self.block(body, payload=pattern if pattern.kind == "payload_pattern" else None)
        elif node.kind == "return":
            if self.function is None:
                self.error(node.token, "E304", "return 只能位于函数内")
            for child in node.children:
                self.expression(child)
        elif node.kind == "shape":
            if len(self.scopes) != 1:
                self.error(node.token, "E103", "shape 仅允许文件顶层")
            self.declare(node, initialized=True)
            fields = set()
            for field in node.children:
                if field.token.lexeme in fields:
                    self.error(field.token, "E301", "结构字段重复声明")
                fields.add(field.token.lexeme)
                self.annotation(field.data)
                for default in field.children:
                    self.expression(default)
        elif node.kind == "block":
            self.block(node)
        elif node.kind == "for":
            self.expression(node.children[0])
            self.loops += 1
            try:
                self.block(node.children[1], loop=node)
            finally:
                self.loops -= 1
        elif node.kind == "while":
            self.expression(node.children[0])
            self.loops += 1
            try:
                self.block(node.children[1])
            finally:
                self.loops -= 1
        elif node.kind == "if":
            for child in node.children:
                self.block(child) if child.kind == "block" else self.expression(child)
        elif node.kind in {"break", "continue"}:
            if not self.loops:
                self.error(node.token, "E304", "break/continue 只能位于当前函数的循环内")
        else:
            for child in node.children:
                self.expression(child)

    def pattern_key(self, node):
        if node.kind == "unary":
            category, value = self.pattern_key(node.children[0])
            return category, -value if node.token.kind == "MINUS" else value
        if node.kind in {"integer", "float"}:
            return "number", self.integers[id(node)]
        return node.kind, node.data

    def expression(self, expression, current=False, pure=False):
        pending = [expression]
        while pending:
            node = pending.pop()
            self.meter.cancellation.check()
            if pure:
                allowed = {"integer", "float", "string", "bool", "null", "quantity", "name", "current",
                           "group", "field", "index", "array", "unary", "add", "binary", "call"}
                if node.kind not in allowed:
                    self.error(node.token, "E307", "查询条目包含不允许的表达式")
                if node.kind == "call":
                    callee = node.children[0]
                    while callee.kind == "group":
                        callee = callee.children[0]
                    if callee.kind == "name":
                        ref = self.lookup(callee.token)
                        valid = ref.symbol in {"len", "str"}
                    elif callee.kind == "field" and callee.children[0].kind == "name":
                        ref = self.lookup(callee.children[0].token)
                        valid = False
                    else:
                        valid = False
                        base = callee
                        while base.kind in {"field", "group"}:
                            base = base.children[0]
                        if base.kind == "name":
                            self.lookup(base.token)
                    if not valid:
                        self.error(callee.token, "E307", "查询只允许白名单的实际原生绑定调用")
            if node.kind == "current":
                if not current:
                    self.error(node.token, "E307", "@ 仅用于查询当前项或管道直接插槽")
                continue
            if node.kind == "query":
                self.expression(node.children[0])
                for clause in node.children[1:]:
                    self.expression(clause.children[0], current=clause.kind != "take", pure=True)
                continue
            if node.kind == "pipe":
                source, call = node.children
                self.expression(source)
                slots = [arg for arg in call.children[1:] if arg.kind == "current"]
                if len(slots) != 1:
                    self.error(node.token, "E103", "管道必须有且仅有一个直接 @ 参数")
                for child in call.children:
                    if child in slots:
                        continue
                    scan = [child]
                    while scan:
                        item = scan.pop()
                        if item.kind == "current":
                            self.error(item.token, "E307", "管道其余表达式不允许 @")
                        scan.extend(item.children)
                    self.expression(child)
                continue
            if node.kind == "propagate":
                fn = self.function.node if self.function else None
                if fn is None or fn.kind != "function" or getattr(fn.data, "kind", None) != "TYPE_RESULT":
                    self.error(node.token, "E304", "? 仅允许显式 Result 具名函数")
            if node.kind == "quantity":
                if node.data.lexeme not in UNITS:
                    self.error(node.data, "E306", "未知单位")
                self.quantities[id(node)] = literal(node.token, node.data.lexeme, self.meter, self.file)
            if node.kind in {"lambda", "lazy"}:
                self.resolve_function(node)
                continue
            if node.kind == "name":
                self.references[id(node)] = self.lookup(node.token)
            if node.kind == "integer":
                value = int(node.data)
                self.meter.check("integer_bits", value.bit_length(), file=self.file, span=node.token.span)
                self.integers[id(node)] = value
            elif node.kind == "float":
                value = float(node.data)
                if not math.isfinite(value):
                    self.error(node.token, "E208", "Float 字面量必须有限")
                self.integers[id(node)] = value
            pending.extend(reversed(node.children))

    def resolve(self):
        for statement in self.root.children:
            self.statement(statement)
        return Program(self.root, MappingProxyType(self.integers),
                       quantities=MappingProxyType(self.quantities), machines=MappingProxyType(self.machines),
                       references=MappingProxyType(self.references), annotations=MappingProxyType(self.annotations),
                       symbols=MappingProxyType(self.symbols), functions=MappingProxyType(self.functions))
