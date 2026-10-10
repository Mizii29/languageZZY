"""Resolve lexical identities and literals without running user expressions."""

import math
from types import MappingProxyType

from .ast_nodes import Program
from .diagnostics import Diagnostic, DiagnosticError, display_path
from .lexer import Lexer
from .parser import Parser


BUILTIN_NAMES = frozenset({"io", "array", "text", "math", "data", "unit", "sketch",
                           "len", "str", "range", "wake"})
IMPLEMENTED_NAMES = frozenset({"io", "array", "len", "str", "range"})


class Resolver:
    def __init__(self, root, meter):
        self.root, self.meter = root, meter
        self.file = display_path(root.token.source.path)
        self.scopes = [{name: name for name in IMPLEMENTED_NAMES}]
        self.integers, self.references, self.annotations = {}, {}, {}
        self.loops = 0

    def error(self, token, code, message):
        raise DiagnosticError(Diagnostic(message, code, self.file, token.span))

    def lookup(self, token):
        name = token.lexeme
        for scope in reversed(self.scopes):
            if name in scope:
                symbol = scope[name]
                if symbol is not None:
                    return symbol
                break
        self.error(token, "E302", f"名称 {name} 尚未声明、正在初始化或尚未实现")

    def declare(self, node):
        name = node.token.lexeme
        if name in self.scopes[-1] or (len(self.scopes) == 1 and name in BUILTIN_NAMES):
            self.error(node.token, "E301", f"名称 {name} 在当前作用域重复声明")
        self.scopes[-1][name] = None

    def annotation(self, annotation):
        if annotation is None:
            return
        if isinstance(annotation, tuple):
            self.annotations[id(annotation[0])] = (self.lookup(annotation[0]),
                                                  tuple(t.lexeme for t in annotation[1:]))
        else:
            self.annotations[id(annotation)] = annotation.lexeme[1:-1]

    def block(self, node, initial=None):
        self.scopes.append(initial or {})
        try:
            for child in node.children:
                self.statement(child)
        finally:
            self.scopes.pop()

    def statement(self, node):
        self.meter.cancellation.check()
        if node.kind == "binding":
            self.declare(node)
            self.annotation(node.data[1])
            self.expression(node.children[0])
            self.scopes[-1][node.token.lexeme] = id(node)
        elif node.kind == "shape":
            if len(self.scopes) != 1:
                self.error(node.token, "E103", "shape 仅允许文件顶层")
            self.declare(node)
            self.scopes[-1][node.token.lexeme] = id(node)
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
                self.block(node.children[1], {node.token.lexeme: id(node)})
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
                if child.kind == "block":
                    self.block(child)
                else:
                    self.expression(child)
        elif node.kind in {"break", "continue"}:
            if not self.loops:
                self.error(node.token, "E304", "break/continue 只能位于当前函数的循环内")
        else:
            for child in node.children:
                self.expression(child)

    def expression(self, expression):
        pending = [expression]
        while pending:
            node = pending.pop()
            self.meter.cancellation.check()
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
                       MappingProxyType(self.references), MappingProxyType(self.annotations))


def prepare(source, meter):
    root = Parser(Lexer(source, meter).scan(), meter).parse()
    return Resolver(root, meter).resolve()
