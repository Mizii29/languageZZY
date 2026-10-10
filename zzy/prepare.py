"""Parse and resolve the entire entry before any observable execution."""

from .ast_nodes import Program
from .diagnostics import Diagnostic, DiagnosticError, display_path
from .lexer import Lexer
from .parser import Parser
from types import MappingProxyType


BUILTIN_NAMES = frozenset({"io", "array", "text", "math", "data", "unit", "sketch",
                           "len", "str", "range", "wake"})


def prepare(source, meter):
    root = Parser(Lexer(source, meter).scan(), meter).parse()
    names = {"io"}
    integers = {}
    file = display_path(source.path)

    def error(node, code, message):
        raise DiagnosticError(Diagnostic(message, code, file, node.token.span))

    def resolve(expression):
        # Iterative traversal also handles long flat sums without host recursion.
        pending = [expression]
        while pending:
            node = pending.pop()
            meter.cancellation.check()
            if node.kind == "name" and node.data not in names:
                error(node, "E302", f"名称 {node.data} 尚未声明或尚未实现")
            if node.kind == "integer":
                # Lexer has already checked the decimal limit, including leading zeroes.
                value = int(node.data)
                meter.check("integer_bits", value.bit_length(), file=file, span=node.token.span)
                integers[id(node)] = value
            pending.extend(reversed(node.children))

    for statement in root.children:
        if statement.kind == "binding":
            name = statement.token.lexeme
            if name in names or name in BUILTIN_NAMES:
                error(statement, "E301", f"名称 {name} 在当前作用域重复声明")
            resolve(statement.children[0])
            names.add(name)
        else:
            resolve(statement)
    return Program(root, MappingProxyType(integers))
