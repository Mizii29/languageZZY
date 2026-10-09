"""Read bounded UTF-8 snapshots; keep original CRLF and code-point offsets."""

from bisect import bisect_right
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path

from .diagnostics import Diagnostic, DiagnosticError, Position, Span, display_path
from .resources import ResourceMeter, Reservation


@dataclass(frozen=True)
class Source:
    path: Path
    raw: bytes
    text: str
    line_starts: tuple[int, ...]
    sha256: str

    @classmethod
    def from_bytes(cls, path: Path, raw: bytes) -> "Source":
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise DiagnosticError(Diagnostic("源码不是合法 UTF-8", "E401", display_path(path))) from None
        starts = (0, *(index + 1 for index, char in enumerate(text) if char == "\n"))
        return cls(path, raw, text, starts, hashlib.sha256(raw).hexdigest())

    def position(self, offset: int) -> Position:
        if type(offset) is not int or not 0 <= offset <= len(self.text):
            raise ValueError("offset outside source")
        line = bisect_right(self.line_starts, offset)
        return Position(line, offset - self.line_starts[line - 1] + 1)

    def span(self, start: int, end: int) -> Span:
        return Span(self.position(start), self.position(end))


class SourceLoader:
    """One preparation session, canonical path identities, no implicit chdir."""

    def __init__(self, meter: ResourceMeter):
        self.meter = meter
        self._sources: dict[str, Source] = {}
        self._reservations: list[Reservation] = []

    def read(self, path: str | Path, *, importer: Path | None = None,
             import_depth: int = 1) -> Source:
        candidate = Path(path)
        if importer is not None and not candidate.is_absolute():
            candidate = importer.parent / candidate
        file = display_path(candidate)
        if type(import_depth) is not int or import_depth < 1:
            raise ValueError("entry import depth is one")
        self.meter.check("import_depth", import_depth, file=file)
        try:
            try:
                canonical = candidate.resolve(strict=True)
            except RuntimeError as error:
                if isinstance(error, RecursionError):
                    raise
                raise OSError(str(error)) from error
            identity = os.path.normcase(str(canonical))
            if identity in self._sources:
                return self._sources[identity]
            self.meter.check("module_count", self.meter.used("module_count") + 1, file=file)
            raw = bytearray()
            with canonical.open("rb") as stream:
                while True:
                    self.meter.cancellation.check()
                    remaining = min(
                        self.meter.policy.limits["source_file_bytes"] - len(raw),
                        self.meter.policy.limits["source_total_bytes"]
                        - self.meter.used("source_total_bytes") - len(raw),
                    )
                    chunk = stream.read(min(65536, remaining + 1))
                    if not chunk:
                        break
                    self.meter.check("source_file_bytes", len(raw) + len(chunk), file=file)
                    self.meter.check("source_total_bytes", self.meter.used("source_total_bytes")
                                     + len(raw) + len(chunk), file=file)
                    raw.extend(chunk)
            reservation = self.meter.reserve(source_total_bytes=len(raw), module_count=1, file=file)
            try:
                source = Source.from_bytes(canonical, bytes(raw))
                self._reservations.append(reservation)
                self._sources[identity] = source
            except BaseException:
                reservation.release()
                raise
            return source
        except (OSError, ValueError) as error:
            raise DiagnosticError(Diagnostic(f"无法读取源码：{error}", "E401", file)) from None

    def close(self):
        self._sources.clear()
        for reservation in self._reservations:
            reservation.release()
        self._reservations.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
