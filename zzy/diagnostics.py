"""Structured diagnostics and phase-specific failure signals."""

from dataclasses import asdict, dataclass, replace
from enum import Enum
import json
import os


class Phase(Enum):
    FRONTEND = 2
    EXECUTION = 1


@dataclass(frozen=True, order=True)
class Position:
    line: int
    column: int

    def __post_init__(self):
        if self.line < 1 or self.column < 1:
            raise ValueError("source positions are one-based")


@dataclass(frozen=True)
class Span:
    start: Position
    end: Position

    def __post_init__(self):
        if self.end < self.start:
            raise ValueError("span end precedes start")


def display_path(path: str | os.PathLike | None) -> str | None:
    if path is None:
        return None
    # Resolve both sides: Windows cwd may retain an 8.3 alias while Source.path
    # already contains the canonical long name. These still name one directory.
    canonical = os.path.realpath(path)
    try:
        return os.path.relpath(canonical, os.path.realpath(os.getcwd())).replace("\\", "/")
    except ValueError:
        return canonical.replace("\\", "/")


@dataclass(frozen=True)
class Diagnostic:
    message: str
    code: str | None = None
    file: str | None = None
    span: Span | None = None
    notes: tuple[str, ...] = ()
    kind: str = "error"

    def __post_init__(self):
        if self.kind not in {"error", "trace", "cancelled", "internal_error"}:
            raise ValueError("unknown diagnostic kind")
        if (self.kind == "error") != (self.code is not None):
            raise ValueError("only errors have error codes")

    def record(self) -> dict:
        return {
            "schema_version": 1,
            "kind": self.kind,
            "code": self.code,
            "file": self.file,
            "span": asdict(self.span) if self.span else None,
            "message": self.message,
            "notes": list(self.notes),
        }


class DiagnosticError(Exception):
    def __init__(self, diagnostic: Diagnostic, phase: Phase = Phase.FRONTEND):
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic
        self.phase = phase

    @property
    def exit_code(self) -> int:
        return self.phase.value


class AbortSignal(BaseException):
    """Context aborts must escape ordinary native-library Exception handlers."""


class Cancelled(AbortSignal):
    pass


class ResourceExceeded(AbortSignal):
    def __init__(self, key: str, limit: int, requested: int, phase: Phase,
                 file: str | None = None, span: Span | None = None):
        self.key, self.limit, self.requested = key, limit, requested
        self.phase = phase
        self.diagnostic = Diagnostic(
            f"资源超限：{key}，上限 {limit}，本次需求 {requested}",
            "E211", file, span,
        )

    @property
    def exit_code(self) -> int:
        return self.phase.value


def _one_line(text: str) -> str:
    return text.replace("\r", "\\r").replace("\n", "\\n")


def render(diagnostic: Diagnostic, format: str = "text", max_bytes: int = 4096) -> str:
    """Fit one complete record, never a sliced UTF-8 or JSON byte sequence."""
    if format not in {"text", "json"} or max_bytes < 512:
        raise ValueError("invalid diagnostic format or reserve")

    def encode(item: Diagnostic) -> str:
        if format == "json":
            return json.dumps(item.record(), ensure_ascii=False, separators=(",", ":")) + "\n"
        where = _one_line(item.file) if item.file is not None else "<cli>"
        if item.span:
            where += f":{item.span.start.line}:{item.span.start.column}"
        label = item.code or item.kind
        text = f"{where}: {label} {_one_line(item.message)}\n"
        return text + "".join(f"  {_one_line(note)}\n" for note in item.notes)

    def size(text: str) -> int:
        return len(text.encode("utf-8", errors="backslashreplace"))

    # Bound temporary formatting too, even if the supplied error is enormous.
    item = replace(diagnostic, message=diagnostic.message[:max_bytes],
                   notes=tuple(n[:max_bytes] for n in diagnostic.notes[:8]))
    if item.file is not None and len(item.file) > max_bytes // 4:
        item = replace(item, file=None, message="定位被省略；" + item.message)
    result = encode(item)
    if size(result) <= max_bytes:
        return result
    item = replace(item, notes=())
    if size(encode(replace(item, message="…"))) > max_bytes:
        item = replace(item, file=None, message="定位被省略；" + item.message)
    low, high = 0, len(item.message)
    while low < high:
        middle = (low + high + 1) // 2
        if size(encode(replace(item, message=item.message[:middle] + "…"))) <= max_bytes:
            low = middle
        else:
            high = middle - 1
    return encode(replace(item, message=item.message[:low] + "…"))
