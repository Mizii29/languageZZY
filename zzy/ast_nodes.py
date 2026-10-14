"""Immutable syntax tree. Tokens retain the original diagnostic positions."""

from dataclasses import dataclass, field
from typing import Mapping
from types import MappingProxyType

from .tokens import Token


@dataclass(frozen=True, slots=True)
class Node:
    kind: str
    token: Token
    children: tuple["Node", ...] = ()
    data: object = None
    depth: int = 0
    start: int = 0
    end: int = 0

    @property
    def span(self):
        return self.token.source.span(self.start, self.end)


@dataclass(frozen=True, slots=True)
class Program:
    root: Node
    # Prepared literals are separate from the immutable syntax tree and runtime.
    integers: Mapping[int, int | float]

    quantities: Mapping[int, object] = field(default_factory=lambda: MappingProxyType({}))
    machines: Mapping[int, object] = field(default_factory=lambda: MappingProxyType({}))
    modules: Mapping[int, Node] = field(default_factory=lambda: MappingProxyType({}))
    sources: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    references: Mapping[int, object] = field(default_factory=lambda: MappingProxyType({}))
    annotations: Mapping[int, object] = field(default_factory=lambda: MappingProxyType({}))
    symbols: Mapping[int, "Symbol"] = field(default_factory=lambda: MappingProxyType({}))
    functions: Mapping[int, "FunctionPlan"] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True, slots=True)
class Reference:
    kind: str
    key: int | str
    symbol: int | str


@dataclass(frozen=True, slots=True)
class Symbol:
    owner: int | None
    slot: int | None
    mutable: bool
    cell: bool = False


@dataclass(frozen=True, slots=True)
class Capture:
    source: Reference
    symbol: int


@dataclass(frozen=True, slots=True)
class FunctionPlan:
    locals: tuple[int, ...]
    captures: tuple[Capture, ...]
    blocks: Mapping[int, tuple[int, ...]]
