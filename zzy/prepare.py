"""Prepare an immutable dependency graph from bounded byte snapshots."""
from dataclasses import replace
import os
from pathlib import Path
from types import MappingProxyType

from .diagnostics import Diagnostic, DiagnosticError, display_path
from .lexer import Lexer
from .parser import Parser
from .resolver import BUILTIN_NAMES, IMPLEMENTED_NAMES, Resolver
from .source import SourceLoader


def identity(path):
    return os.path.normcase(str(Path(path).resolve()))


def prepare(source, meter, loader=None):
    if loader is None:
        with SourceLoader(meter) as owned:
            # The caller already read the root. Seed the same identity without rereading.
            owned._sources[identity(source.path)] = source
            return prepare(source, meter, owned)
    active, finished, modules, sources = set(), {}, {}, {}
    def visit(current, depth, site=None):
        key = identity(current.path)
        if key in active:
            raise DiagnosticError(Diagnostic('循环模块导入','E303',display_path(site.token.source.path),site.data.span))
        if key in finished:
            return finished[key]
        active.add(key)
        sources[key] = current
        root = Parser(Lexer(current,meter).scan(),meter).parse()
        program = Resolver(root,meter).resolve()
        for node in root.children:
            if node.kind != 'use':continue
            if Path(node.data.value).suffix != '.zzy':
                raise DiagnosticError(Diagnostic('模块扩展名必须为 .zzy','E303',display_path(current.path),node.data.span))
            try:
                dependency=loader.read(node.data.value,importer=current.path,import_depth=depth+1)
            except DiagnosticError as error:
                raise DiagnosticError(Diagnostic('无法读取导入模块：'+error.diagnostic.message,'E303',display_path(current.path),node.data.span)) from None
            modules[id(node)] = visit(dependency,depth+1,node).root
        active.remove(key)
        finished[key]=program
        return program
    entry=visit(source,1)
    mappings={name:{} for name in ('integers','quantities','machines','references','annotations','symbols','functions')}
    for program in finished.values():
        for name in mappings:mappings[name].update(getattr(program,name))
    return replace(entry,**{k:MappingProxyType(v) for k,v in mappings.items()},
                   modules=MappingProxyType(modules),sources=MappingProxyType(sources))
