"""Recursive descent for the explicitly supported P01 subset."""

from .ast_nodes import Node
from .diagnostics import Diagnostic, DiagnosticError, display_path
from .resources import ResourceMeter
from .tokens import Token


class Parser:
    def __init__(self, tokens: list[Token], meter: ResourceMeter):
        self.tokens, self.meter = tokens, meter
        self.index = 0
        self.nesting = 0
        self.file = display_path(tokens[0].source.path)

    @property
    def current(self):
        return self.tokens[self.index]

    def advance(self):
        token = self.current
        if token.kind != "EOF":
            self.index += 1
        self.meter.cancellation.check()
        return token

    def accept(self, kind):
        return self.advance() if self.current.kind == kind else None

    def expect(self, kind, description):
        if self.current.kind != kind:
            self.error(self.current, f"需要{description}；当前词项为 {self.current.lexeme or 'EOF'}")
        return self.advance()

    def error(self, token, message):
        raise DiagnosticError(Diagnostic(message, "E103", self.file, token.span))

    def node(self, kind, token, children=(), data=None, end=None):
        depth = max((child.depth + 1 for child in children), default=0)
        self.meter.check("syntax_depth", depth, file=self.file, span=token.span)
        self.meter.consume("ast_nodes_total", 1, file=self.file, span=token.span)
        start = min((child.start for child in children), default=token.start)
        finish = max((child.end for child in children), default=token.end)
        return Node(kind, token, tuple(children), data, depth,
                    min(start, token.start), max(finish, end or token.end))

    def parse(self):
        statements = []
        first = self.current
        while self.current.kind != "EOF":
            statements.append(self.statement())
        return self.node("program", first, statements)

    def statement(self):
        if self.current.kind in {"IMMUTABLE_DECL", "MUTABLE_DECL"}:
            declaration = self.advance()
            name = self.expect("IDENT", "声明名称")
            annotation = None
            if self.accept("COLON"):
                annotation = self.current
                if annotation.kind not in {"TYPE_INT", "TYPE_STRING", "TYPE_NULL", "TYPE_FUNCTION"}:
                    self.error(annotation, "P01 尚不支持此类型注解")
                self.advance()
            self.expect("INIT", ":=")
            value = self.expression()
            self.expect("SEMICOLON", "分号 ;")
            return self.node("binding", name, (value,),
                             (declaration.kind == "MUTABLE_DECL", annotation))
        expression = self.expression()
        if self.accept("ASSIGN"):
            base = expression
            while base.kind == "field":
                base = base.children[0]
            if base.kind != "name":
                self.error(expression.token, "赋值目标必须为名称或字段；P01 尚不支持下标")
            value = self.expression()
            self.expect("SEMICOLON", "分号 ;")
            return self.node("assignment", expression.token, (expression, value))
        self.expect("SEMICOLON", "分号 ;")
        return self.node("expression", expression.token, (expression,))

    def expression(self):
        left = self.postfix()
        while self.current.kind == "PLUS":
            operator = self.advance()
            left = self.node("add", operator, (left, self.postfix()))
        return left

    def nested(self, opening):
        self.nesting += 1
        try:
            self.meter.check("syntax_depth", self.nesting, file=self.file, span=opening.span)
            return self.expression()
        finally:
            self.nesting -= 1

    def postfix(self):
        value = self.primary()
        while self.current.kind in {"DOT", "LEFT_PAREN"}:
            if self.accept("DOT"):
                name = self.expect("IDENT", "字段名称")
                value = self.node("field", name, (value,), name.lexeme)
            else:
                opening = self.advance()
                args = []
                if self.current.kind != "RIGHT_PAREN":
                    while True:
                        args.append(self.nested(opening))
                        if not self.accept("COMMA") or self.current.kind == "RIGHT_PAREN":
                            break
                closing = self.expect("RIGHT_PAREN", "右括号 )")
                value = self.node("call", opening, (value, *args), end=closing.end)
        return value

    def primary(self):
        token = self.advance()
        if token.kind in {"INTEGER", "STRING", "IDENT"}:
            kind = {"INTEGER": "integer", "STRING": "string", "IDENT": "name"}[token.kind]
            return self.node(kind, token, data=token.value if kind == "string" else token.lexeme)
        if token.kind == "RAW":
            string = self.expect("STRING", "raw 字符串")
            return self.node("string", token, data=string.value, end=string.end)
        if token.kind == "LEFT_PAREN":
            value = self.nested(token)
            closing = self.expect("RIGHT_PAREN", "右括号 )")
            # Keep grouping to reject `(name) <- value` per the target grammar.
            return self.node("group", token, (value,), end=closing.end)
        self.error(token, "需要表达式；P01 仅支持 Int、String、名称、分组、加法和普通调用")
