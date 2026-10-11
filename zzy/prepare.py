"""Prepare a complete immutable program without executing user expressions."""

from .lexer import Lexer
from .parser import Parser
from .resolver import BUILTIN_NAMES, IMPLEMENTED_NAMES, Resolver


def prepare(source, meter):
    root = Parser(Lexer(source, meter).scan(), meter).parse()
    return Resolver(root, meter).resolve()
