"""Forward-only lexer with separate normal, comment, and string modes."""

from .diagnostics import Diagnostic, DiagnosticError, display_path
from .resources import ResourceMeter
from .source import Source
from .tokens import FIXED_TOKENS, RESERVED_NAMES, SYMBOLS_BY_FIRST, Token


def identifier_continue(char: str) -> bool:
    # Fixed-size checks preserve Python's Unicode identifier rules without
    # repeatedly rescanning a growing identifier or normalizing its spelling.
    return bool(char) and ("a" + char).isidentifier()


def ascii_digit(char: str) -> bool:
    return "0" <= char <= "9"


class Lexer:
    def __init__(self, source: Source, meter: ResourceMeter):
        self.source = source
        self.text = source.text
        self.meter = meter
        self.file = display_path(source.path)
        self.index = 0
        self.count = 0
        self._raw_start: int | None = None

    def _peek(self, ahead: int = 0) -> str:
        index = self.index + ahead
        return self.text[index] if index < len(self.text) else ""

    def _advance(self, amount: int = 1):
        previous = self.index
        self.index += amount
        if previous // 1024 != self.index // 1024:
            self.meter.cancellation.check()

    def _error(self, code: str, message: str, start: int, end: int):
        raise DiagnosticError(Diagnostic(message, code, self.file, self.source.span(start, end)))

    def _check(self, key: str, requested: int, start: int, end: int):
        self.meter.check(key, requested, file=self.file, span=self.source.span(start, end))

    def _skip_comment(self, start: int, multiline: bool):
        if not multiline:
            while self._peek() and self._peek() not in "\r\n":
                self._advance()
            return
        while self._peek():
            if self.text.startswith("zzyend", self.index):
                before = self.text[self.index - 1] if self.index else ""
                after = self.text[self.index + 6:self.index + 7]
                if not identifier_continue(before) and not identifier_continue(after):
                    self._advance(6)
                    return
                self._advance(6)
            else:
                self._advance()
        self._error("E101", "多行注释未闭合，缺少完整结束词 zzyend", start, start + 11)

    def _skip_trivia(self):
        while self._peek():
            self.meter.cancellation.check()
            if self._peek().isspace():
                self._advance()
                continue
            # Whole identifiers are scanned below; the left boundary prevents
            # consuming a suffix of a preceding number/name as a comment.
            before = self.text[self.index - 1] if self.index else ""
            if not identifier_continue(before):
                if self.text.startswith("zzysayalot:", self.index):
                    start = self.index
                    self._advance(11)
                    self._skip_comment(start, True)
                    continue
                if self.text.startswith("zzysay:", self.index):
                    start = self.index
                    self._advance(7)
                    self._skip_comment(start, False)
                    continue
            return

    def _number(self, start: int) -> Token:
        digits = 0
        kind = "INTEGER"
        while ascii_digit(self._peek()):
            self._advance()
            digits += 1
            self._check("numeric_digits", digits, start, self.index)
        if self._peek() == "." and ascii_digit(self._peek(1)):
            kind = "FLOAT"
            self._advance()
            while ascii_digit(self._peek()):
                self._advance()
                digits += 1
                self._check("numeric_digits", digits, start, self.index)
        return Token(kind, self.source, start, self.index)

    def _string(self, start: int, raw: bool) -> Token:
        self._advance()
        pieces: list[str] = []
        length = 0
        escapes = {"n": "\n", "t": "\t", "r": "\r", "q": '"', "b": "\\"}
        while self._peek():
            char = self._peek()
            if char == '"':
                self._advance()
                return Token("STRING", self.source, start, self.index, "".join(pieces), raw)
            if char in "\r\n":
                self._error("E101", "字符串不能包含物理换行", start, start + 1)
            if not raw and self.text.startswith("[OoO]", self.index):
                escape_start = self.index
                self._advance(5)
                if self.text.startswith("[OoO]", self.index):
                    piece = "[OoO]"
                    self._advance(5)
                elif self._peek() in escapes:
                    piece = escapes[self._peek()]
                    self._advance()
                else:
                    end = self.index + (1 if self._peek() and self._peek() != '"' else 0)
                    self._error("E102", "未知或未完成的 [OoO] 转义", escape_start, end)
            else:
                piece = char
                self._advance()
            length += len(piece)
            self._check("text_codepoints", length, start, self.index)
            pieces.append(piece)
        self._error("E101", "字符串未闭合", start, start + 1)

    def scan(self) -> list[Token]:
        tokens = []
        while True:
            self.meter.cancellation.check()
            self._skip_trivia()
            start = self.index
            char = self._peek()
            if self._raw_start is not None and char != '"':
                self._error("E101", "(raw) 后必须是双引号字符串",
                            self._raw_start, self._raw_start + 5)
            if not char:
                tokens.append(Token("EOF", self.source, start, start))
                return tokens
            self._check("tokens_per_file", self.count + 1, start, start + 1)
            if char == '"':
                token = self._string(start, self._raw_start is not None)
                self._raw_start = None
            elif ascii_digit(char):
                token = self._number(start)
            elif char.isidentifier():
                self._advance()
                while identifier_continue(self._peek()):
                    self._advance()
                name = self.text[start:self.index]
                if name == "zzyend":
                    self._error("E101", "zzyend 只能结束多行注释", start, self.index)
                kind = "WILDCARD" if name == "_" else (
                    "RESERVED_NAME" if name in RESERVED_NAMES else "IDENT")
                token = Token(kind, self.source, start, self.index)
            else:
                for spelling in SYMBOLS_BY_FIRST.get(char, ()):
                    if self.text.startswith(spelling, start):
                        self._advance(len(spelling))
                        token = Token(FIXED_TOKENS[spelling], self.source, start, self.index)
                        if token.kind == "RAW":
                            self._raw_start = start
                        break
                else:
                    self._error("E101", f"非法字符 {char!r}", start, start + 1)
            tokens.append(token)
            self.count += 1
