"""Token spellings from syntax v0.6; numeric conversion belongs to preparation."""

from dataclasses import asdict, dataclass
from types import MappingProxyType

from .source import Source


FIXED_TOKENS = MappingProxyType({
    "(zno)": "IMMUTABLE_DECL", "(zyes)": "MUTABLE_DECL",
    "(addnew)": "FUNCTION", "(return)": "RETURN",
    "(zif?:)": "IF", "(zzif?:)": "ELIF", "(zzyf:)": "ELSE",
    "(for)": "FOR", "(in)": "IN", "(while)": "WHILE",
    "(break)": "BREAK", "(continue)": "CONTINUE",
    "(shape)": "SHAPE", "(machine)": "MACHINE", "(with)": "WITH",
    "(and)": "AND", "(or)": "OR", "(not)": "NOT",
    "(true)": "TRUE", "(false)": "FALSE", "(null)": "NULL",
    "(raw)": "RAW", "(zzz)": "LAZY", "(spec)": "SPEC",
    "(use)": "USE", "(as)": "AS",
    "(keep)": "KEEP", "(order)": "ORDER", "(take)": "TAKE",
    "(yield)": "YIELD", "(asc)": "ASC", "(desc)": "DESC",
    "(Int)": "TYPE_INT", "(Float)": "TYPE_FLOAT", "(String)": "TYPE_STRING",
    "(Bool)": "TYPE_BOOL", "(Null)": "TYPE_NULL", "(Array)": "TYPE_ARRAY",
    "(Map)": "TYPE_MAP", "(Function)": "TYPE_FUNCTION", "(Result)": "TYPE_RESULT",
    "(Lazy)": "TYPE_LAZY", "(Range)": "TYPE_RANGE", "(Machine)": "TYPE_MACHINE",
    "(Quantity)": "TYPE_QUANTITY",
    "(^_^)": "SUCCESS", "(T_T)": "FAILURE", "(?_?)": "MATCH",
    "(o_o)": "ASSERT", "(@_@)": "TRACE",
    ":=": "INIT", "<-": "ASSIGN", "::": "DOUBLE_COLON", "=>": "FAT_ARROW",
    "-->": "STATE_ARROW", "--": "STATE_EDGE", "->": "ARROW", "<<": "SEND",
    "..<": "INTERVAL", "~>": "PIPE", "?>": "QUERY", "//": "FLOOR_DIVIDE",
    "<=": "LESS_EQUAL", ">=": "GREATER_EQUAL", "==": "EQUAL", "!=": "NOT_EQUAL",
    "(": "LEFT_PAREN", ")": "RIGHT_PAREN", "[": "LEFT_BRACKET", "]": "RIGHT_BRACKET",
    "{": "LEFT_BRACE", "}": "RIGHT_BRACE", ";": "SEMICOLON", ":": "COLON",
    ",": "COMMA", ".": "DOT", "?": "QUESTION", "@": "AT",
    "+": "PLUS", "-": "MINUS", "*": "MULTIPLY", "/": "DIVIDE", "%": "REMAINDER",
    "<": "LESS", ">": "GREATER",
})

# Emoticon contents are not bare keywords. Reserved spellings remain distinct
# from ordinary names; a later Parser decides whether a name is allowed there.
RESERVED_NAMES = frozenset({
    "zno", "zyes", "addnew", "return", "zif", "zzif", "zzyf", "for", "in", "while",
    "break", "continue", "shape", "machine", "with", "and", "or", "not", "true",
    "false", "null", "raw", "zzz", "spec", "use", "as", "keep", "order", "take",
    "yield", "asc", "desc", "Int", "Float", "String", "Bool", "Null", "Array", "Map",
    "Function", "Result", "Lazy", "Range", "Machine", "Quantity", "zzysay", "zzysayalot",
})

SYMBOLS_BY_FIRST = MappingProxyType({
    first: tuple(sorted((symbol for symbol in FIXED_TOKENS if symbol[0] == first),
                        key=len, reverse=True))
    for first in {symbol[0] for symbol in FIXED_TOKENS}
})


@dataclass(frozen=True, slots=True)
class Token:
    kind: str
    source: Source
    start: int
    end: int
    value: str | None = None
    raw: bool = False

    @property
    def lexeme(self) -> str:
        return self.source.text[self.start:self.end]

    @property
    def span(self):
        return self.source.span(self.start, self.end)

    def record(self) -> dict:
        return {"schema_version": 1, "kind": self.kind, "lexeme": self.lexeme,
                "value": self.value, "raw": self.raw, "span": asdict(self.span)}
