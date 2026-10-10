"""Immutable P01 syntax tree. Tokens retain the original diagnostic positions."""

from dataclasses import dataclass
from typing import Mapping

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
    integers: Mapping[int, int]
