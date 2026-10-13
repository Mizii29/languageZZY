"""Bounded recursive descent and precedence parsing for P04."""

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

    def annotation(self):
        token = self.current
        if token.kind in {"TYPE_INT", "TYPE_FLOAT", "TYPE_STRING", "TYPE_BOOL",
                          "TYPE_NULL", "TYPE_ARRAY", "TYPE_FUNCTION", "TYPE_RANGE",
                          "TYPE_RESULT", "TYPE_LAZY", "TYPE_MACHINE", "TYPE_QUANTITY"}:
            return self.advance()
        if token.kind == "IDENT":
            parts = [self.advance()]
            while self.accept("DOT"):
                parts.append(self.expect("IDENT", "类型名称"))
            return tuple(parts)
        self.error(token, "此类型注解尚未实现")

    def block(self):
        opening = self.expect("LEFT_BRACE", "左花括号 {")
        self.nesting += 1
        try:
            self.meter.check("syntax_depth", self.nesting, file=self.file, span=opening.span)
            statements = []
            while self.current.kind not in {"RIGHT_BRACE", "EOF"}:
                statements.append(self.statement())
            closing = self.expect("RIGHT_BRACE", "右花括号 }")
            return self.node("block", opening, statements, end=closing.end)
        finally:
            self.nesting -= 1

    def function(self, named):
        keyword = self.expect("FUNCTION", "(addnew)")
        name = self.expect("IDENT", "函数名称") if named else keyword
        self.expect("LEFT_PAREN", "左括号 (")
        parameters = []
        if self.current.kind != "RIGHT_PAREN":
            while True:
                parameter = self.expect("IDENT", "参数名称")
                annotation = self.annotation() if self.accept("COLON") else None
                parameters.append(self.node("parameter", parameter, data=annotation))
                if not self.accept("COMMA") or self.current.kind == "RIGHT_PAREN":
                    break
        self.expect("RIGHT_PAREN", "右括号 )")
        annotation = self.annotation() if named and self.accept("ARROW") else None
        if named:
            body = self.block()
        else:
            self.expect("FAT_ARROW", "匿名函数的 =>")
            body = self.nested(keyword)
        return self.node("function" if named else "lambda", name, (*parameters, body), annotation)

    def pattern(self):
        token = self.current
        if token.kind == "WILDCARD":
            self.advance()
            return self.node("wildcard", token)
        if token.kind in {"SUCCESS", "FAILURE"}:
            self.advance()
            self.expect("LEFT_PAREN", "左括号 (")
            name = self.expect("IDENT", "载荷绑定名称")
            self.expect("RIGHT_PAREN", "右括号 )")
            return self.node("payload_pattern", name, data=token.kind)
        sign = self.advance() if token.kind in {"PLUS", "MINUS"} else None
        if self.current.kind not in ({"INTEGER", "FLOAT"} if sign else
                {"INTEGER", "FLOAT", "STRING", "RAW", "TRUE", "FALSE", "NULL"}):
            self.error(self.current, "需要标量常量或 Result 模式")
        value = self.primary()
        if value.kind == "quantity":
            self.error(value.token, "Quantity 不支持常量模式")
        if sign:
            value = self.node("unary", sign, (value,))
        return self.node("constant_pattern", token, (value,))

    def query(self, source, token):
        self.expect("LEFT_BRACE", "查询块 {")
        clauses = []
        for kind in ("KEEP", "ORDER", "TAKE", "YIELD"):
            if self.current.kind != kind:
                if kind == "YIELD":
                    self.error(self.current, "查询需要按顺序包含唯一 yield")
                continue
            keyword = self.advance()
            self.expect("COLON", "冒号 :")
            value = self.nested(keyword)
            direction = self.advance().kind if kind == "ORDER" and self.current.kind in {"ASC", "DESC"} else "ASC"
            self.expect("SEMICOLON", "分号 ;")
            clauses.append(self.node(kind.lower(), keyword, (value,), direction))
        closing = self.expect("RIGHT_BRACE", "查询结束 }")
        return self.node("query", token, (source, *clauses), end=closing.end)

    def statement(self):
        if self.current.kind in {"ASSERT", "TRACE"}:
            token = self.advance()
            value = self.expression()
            self.expect("SEMICOLON", "分号 ;")
            return self.node(token.kind.lower(), token, (value,))
        if self.current.kind == "SPEC":
            token = self.advance()
            name = self.expect("STRING", "测试名称字符串")
            return self.node("spec", token, (self.block(),), name.value)
        if self.current.kind == "MACHINE":
            self.advance()
            name = self.expect("IDENT", "状态机名称")
            self.expect("LEFT_BRACE", "左花括号 {")
            edges = []
            while self.current.kind not in {"RIGHT_BRACE", "EOF"}:
                start = self.expect("IDENT", "源状态标签")
                self.expect("STATE_EDGE", "--")
                event = self.expect("STRING", "事件字符串")
                self.expect("STATE_ARROW", "-->")
                end = self.expect("IDENT", "目标状态标签")
                self.expect("SEMICOLON", "分号 ;")
                edges.append(self.node("edge", event, data=(start.lexeme, event.value, end.lexeme)))
            closing = self.expect("RIGHT_BRACE", "右花括号 }")
            return self.node("machine", name, edges, end=closing.end)
        if self.current.kind == "MATCH":
            token = self.advance()
            value = self.expression()
            self.expect("LEFT_BRACE", "匹配块 {")
            arms = []
            while self.current.kind not in {"RIGHT_BRACE", "EOF"}:
                pattern = self.pattern()
                self.expect("FAT_ARROW", "分支 =>")
                arms.append(self.node("arm", pattern.token, (pattern, self.block())))
            closing = self.expect("RIGHT_BRACE", "右花括号 }")
            if not arms:
                self.error(closing, "匹配至少需要一个分支")
            return self.node("match", token, (value, *arms), end=closing.end)
        if self.current.kind == "FUNCTION" and self.tokens[self.index + 1].kind == "IDENT":
            return self.function(named=True)
        if self.current.kind == "RETURN":
            token = self.advance()
            values = () if self.current.kind == "SEMICOLON" else (self.expression(),)
            self.expect("SEMICOLON", "分号 ;")
            return self.node("return", token, values)
        if self.current.kind == "LEFT_BRACE":
            return self.block()
        if self.current.kind in {"IMMUTABLE_DECL", "MUTABLE_DECL"}:
            declaration = self.advance()
            name = self.expect("IDENT", "声明名称")
            annotation = self.annotation() if self.accept("COLON") else None
            self.expect("INIT", ":=")
            value = self.expression()
            self.expect("SEMICOLON", "分号 ;")
            return self.node("binding", name, (value,),
                             (declaration.kind == "MUTABLE_DECL", annotation))
        if self.current.kind == "SHAPE":
            self.advance()
            name = self.expect("IDENT", "结构名称")
            self.expect("LEFT_BRACE", "左花括号 {")
            fields = []
            while self.current.kind not in {"RIGHT_BRACE", "EOF"}:
                field = self.expect("IDENT", "字段名称")
                annotation = self.annotation() if self.accept("COLON") else None
                default = (self.expression(),) if self.accept("INIT") else ()
                self.expect("SEMICOLON", "分号 ;")
                fields.append(self.node("definition_field", field, default, annotation))
            closing = self.expect("RIGHT_BRACE", "右花括号 }")
            return self.node("shape", name, fields, end=closing.end)
        if self.current.kind == "IF":
            token = self.advance()
            children = [self.expression(), self.block()]
            while self.accept("ELIF"):
                children.extend((self.expression(), self.block()))
            if self.accept("ELSE"):
                children.append(self.block())
            return self.node("if", token, children)
        if self.current.kind == "WHILE":
            token = self.advance()
            return self.node("while", token, (self.expression(), self.block()))
        if self.current.kind == "FOR":
            self.advance()
            name = self.expect("IDENT", "循环变量")
            self.expect("IN", "(in)")
            return self.node("for", name, (self.expression(), self.block()))
        if self.current.kind in {"BREAK", "CONTINUE"}:
            token = self.advance()
            self.expect("SEMICOLON", "分号 ;")
            return self.node(token.kind.lower(), token)
        expression = self.expression()
        if self.accept("ASSIGN"):
            base = expression
            while base.kind in {"field", "index"}:
                base = base.children[0]
            if base.kind != "name":
                self.error(expression.token, "赋值目标必须为名称、字段或下标")
            value = self.expression()
            self.expect("SEMICOLON", "分号 ;")
            return self.node("assignment", expression.token, (expression, value))
        self.expect("SEMICOLON", "分号 ;")
        return self.node("expression", expression.token, (expression,))

    PRECEDENCE = {"OR": 20, "AND": 30, "EQUAL": 40, "NOT_EQUAL": 40,
                  "LESS": 45, "LESS_EQUAL": 45, "GREATER": 45, "GREATER_EQUAL": 45,
                  "INTERVAL": 50, "PLUS": 60, "MINUS": 60, "MULTIPLY": 70,
                  "DIVIDE": 70, "FLOOR_DIVIDE": 70, "REMAINDER": 70}
    COMPARISONS = {"EQUAL", "NOT_EQUAL", "LESS", "LESS_EQUAL", "GREATER", "GREATER_EQUAL"}

    def expression(self, minimum=0):
        if self.current.kind in {"PLUS", "MINUS", "NOT"}:
            token = self.advance()
            self.nesting += 1
            try:
                self.meter.check("syntax_depth", self.nesting, file=self.file, span=token.span)
                left = self.node("unary", token, (self.expression(35 if token.kind == "NOT" else 80),))
            finally:
                self.nesting -= 1
        else:
            left = self.postfix()
        while True:
            if self.current.kind == "QUERY" and minimum <= 15:
                left = self.query(left, self.advance())
                continue
            if self.current.kind == "PIPE" and minimum <= 0:
                token = self.advance()
                function = self.postfix(calls=False)
                opening = self.expect("LEFT_PAREN", "管道调用 (")
                args = self.arguments(opening, "RIGHT_PAREN")
                closing = self.expect("RIGHT_PAREN", "右括号 )")
                call = self.node("call", opening, (function, *args), end=closing.end)
                left = self.node("pipe", token, (left, call))
                continue
            if self.current.kind == "SEND" and minimum <= 5:
                token = self.advance()
                if left.kind == "send":
                    self.error(token, "同层只允许一次发送")
                left = self.node("send", token, (left, self.expression(6)))
                continue
            if self.current.kind == "WITH" and minimum <= 10:
                token = self.advance()
                fields, closing = self.initializers()
                left = self.node("with", token, (left, *fields), end=closing.end)
                continue
            precedence = self.PRECEDENCE.get(self.current.kind, -1)
            if precedence < minimum:
                break
            operator = self.advance()
            right = self.expression(precedence + 1)
            if operator.kind in self.COMPARISONS:
                if any(child.kind == "binary" and child.token.kind in self.COMPARISONS
                       for child in (left, right)):
                    self.error(operator, "比较不能连续使用；需要显式分组")
            if operator.kind == "INTERVAL" and left.kind == "binary" and left.token.kind == "INTERVAL":
                self.error(operator, "区间不能连续使用")
            left = self.node("add" if operator.kind == "PLUS" else "binary", operator, (left, right))
        return left

    def nested(self, opening):
        self.nesting += 1
        try:
            self.meter.check("syntax_depth", self.nesting, file=self.file, span=opening.span)
            return self.expression()
        finally:
            self.nesting -= 1

    def initializers(self):
        opening = self.expect("LEFT_BRACE", "左花括号 {")
        fields = []
        if self.current.kind != "RIGHT_BRACE":
            while True:
                name = self.expect("IDENT", "字段名称")
                self.expect("COLON", "冒号 :")
                fields.append(self.node("initializer", name, (self.nested(opening),), name.lexeme))
                if not self.accept("COMMA") or self.current.kind == "RIGHT_BRACE":
                    break
        return fields, self.expect("RIGHT_BRACE", "右花括号 }")

    def postfix(self, calls=True):
        value = self.primary()
        while self.current.kind in {"DOT", "LEFT_PAREN", "LEFT_BRACKET", "DOUBLE_COLON", "QUESTION"}:
            if not calls and self.current.kind in {"LEFT_PAREN", "QUESTION"}:
                break
            if self.current.kind == "QUESTION":
                value = self.node("propagate", self.advance(), (value,))
                continue
            if self.accept("DOT"):
                name = self.expect("IDENT", "字段名称")
                value = self.node("field", name, (value,), name.lexeme)
            elif self.accept("DOUBLE_COLON"):
                base = value
                while base.kind == "field":
                    base = base.children[0]
                if base.kind != "name":
                    self.error(value.token, "结构构造需要限定名称")
                fields, closing = self.initializers()
                value = self.node("construct", value.token, (value, *fields), end=closing.end)
            elif self.current.kind == "LEFT_BRACKET":
                opening = self.advance()
                index = self.nested(opening)
                closing = self.expect("RIGHT_BRACKET", "右方括号 ]")
                value = self.node("index", opening, (value, index), end=closing.end)
            else:
                opening = self.advance()
                args = self.arguments(opening, "RIGHT_PAREN")
                closing = self.expect("RIGHT_PAREN", "右括号 )")
                value = self.node("call", opening, (value, *args), end=closing.end)
        return value

    def arguments(self, opening, ending):
        args = []
        if self.current.kind != ending:
            while True:
                args.append(self.nested(opening))
                if not self.accept("COMMA") or self.current.kind == ending:
                    break
        return args

    def primary(self):
        if self.current.kind == "FUNCTION":
            return self.function(named=False)
        token = self.advance()
        if token.kind == "AT":
            return self.node("current", token)
        if token.kind in {"SUCCESS", "FAILURE", "LAZY"}:
            opening = self.expect("LEFT_PAREN", "左括号 (")
            value = self.nested(opening)
            closing = self.expect("RIGHT_PAREN", "右括号 )")
            return self.node("lazy" if token.kind == "LAZY" else "result", token,
                             (value,), token.kind, end=closing.end)
        if token.kind in {"INTEGER", "FLOAT"} and self.accept("DOUBLE_COLON"):
            unit = self.expect("IDENT", "单位名称")
            return self.node("quantity", token, data=unit, end=unit.end)
        kinds = {"INTEGER": "integer", "FLOAT": "float", "STRING": "string", "IDENT": "name",
                 "TRUE": "bool", "FALSE": "bool", "NULL": "null"}
        if token.kind in kinds:
            kind = kinds[token.kind]
            data = token.value if kind == "string" else token.lexeme
            if kind == "bool":
                data = token.kind == "TRUE"
            return self.node(kind, token, data=data)
        if token.kind == "RAW":
            string = self.expect("STRING", "raw 字符串")
            return self.node("string", token, data=string.value, end=string.end)
        if token.kind == "LEFT_PAREN":
            value = self.nested(token)
            closing = self.expect("RIGHT_PAREN", "右括号 )")
            return self.node("group", token, (value,), end=closing.end)
        if token.kind == "LEFT_BRACKET":
            items = self.arguments(token, "RIGHT_BRACKET")
            closing = self.expect("RIGHT_BRACKET", "右方括号 ]")
            return self.node("array", token, items, end=closing.end)
        self.error(token, "需要表达式；此语法尚未实现或位置不合法")
