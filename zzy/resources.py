"""default-v1 policy, bounded configuration, and explicit resource ownership."""

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import sys
from threading import Event
from types import MappingProxyType
from collections.abc import Mapping

from .diagnostics import (Cancelled, Diagnostic, DiagnosticError, Phase,
                          ResourceExceeded, display_path)


DEFAULT_LIMITS = MappingProxyType({
    "source_file_bytes": 2 * 1024**2,
    "source_total_bytes": 16 * 1024**2,
    "module_count": 128,
    "import_depth": 32,
    "tokens_per_file": 250_000,
    "ast_nodes_total": 500_000,
    "syntax_depth": 64,
    "numeric_digits": 4096,
    "integer_bits": 65_536,
    "quantity_exponent_abs": 64,
    "call_depth": 64,
    "value_depth": 64,
    "container_items": 1_000_000,
    "text_codepoints": 4_194_304,
    "io_payload_bytes": 16 * 1024**2,
    "runtime_objects": 200_000,
    "runtime_slots": 2_000_000,
    "runtime_payload_bytes": 128 * 1024**2,
    "stdout_bytes": 1024**2,
    "stderr_bytes": 1024**2,
    "program_cache_entries": 32,
    "program_cache_bytes": 64 * 1024**2,
})
CONFIG_MAX_BYTES = 64 * 1024


def _config_error(message: str, file: str | None = None) -> DiagnosticError:
    return DiagnosticError(Diagnostic(message, "E401", file))


@dataclass(frozen=True)
class ResourcePolicy:
    limits: Mapping[str, int] = field(default_factory=lambda: DEFAULT_LIMITS)
    host_decimal_digits: int = field(default_factory=sys.get_int_max_str_digits)

    def __post_init__(self):
        merged = dict(DEFAULT_LIMITS)
        for key, value in self.limits.items():
            if key not in merged:
                raise _config_error(f"未知资源键：{key}")
            if type(value) is not int or not 1 <= value <= sys.maxsize:
                raise _config_error(f"{key} 必须为 1..{sys.maxsize} 的整数（不含 Bool）")
            merged[key] = value
        if type(self.host_decimal_digits) is not int or self.host_decimal_digits < 0:
            raise ValueError("invalid host decimal limit")
        object.__setattr__(self, "limits", MappingProxyType(merged))

    @property
    def decimal_digits(self) -> int:
        limit = self.limits["numeric_digits"]
        return min(limit, self.host_decimal_digits) if self.host_decimal_digits else limit

    def effective_record(self) -> dict:
        return {"policy_version": 1, "profile": "default-v1", "limits": dict(self.limits),
                "host_decimal_digits": self.host_decimal_digits,
                "effective_decimal_digits": self.decimal_digits}

    @property
    def canonical_json(self) -> str:
        return json.dumps(self.effective_record(), sort_keys=True, separators=(",", ":"))

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json.encode("utf-8")).hexdigest()

    @classmethod
    def from_file(cls, path: str | Path) -> "ResourcePolicy":
        file = display_path(path)

        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError(f"重复配置键：{key}")
                result[key] = value
            return result

        def integer(text):
            # Values outside Py_ssize_t are not supported by this implementation.
            if len(text.lstrip("-")) > len(str(sys.maxsize)):
                raise ValueError(f"配置整数超出 1..{sys.maxsize}")
            return int(text)

        def invalid_number(text):
            raise ValueError(f"配置不接受非整数数值：{text[:40]}")

        try:
            with open(path, "rb") as stream:
                data = stream.read(CONFIG_MAX_BYTES + 1)
            if len(data) > CONFIG_MAX_BYTES:
                raise ValueError("资源配置文件超过 64 KiB")
            config = json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                                parse_int=integer, parse_float=invalid_number,
                                parse_constant=invalid_number)
            if type(config) is not dict or set(config) != {"policy_version", "limits"}:
                raise ValueError("配置只接受 policy_version 和 limits 两个必需字段")
            if type(config["policy_version"]) is not int or config["policy_version"] != 1:
                raise ValueError("仅支持 policy_version: 1")
            if type(config["limits"]) is not dict:
                raise ValueError("limits 必须为对象")
            return cls(config["limits"])
        except DiagnosticError as error:
            raise _config_error(error.diagnostic.message, file) from None
        except (OSError, ValueError, RecursionError) as error:
            raise _config_error(f"无法加载资源配置：{error}", file) from None


class CancellationToken:
    def __init__(self):
        self._event = Event()

    def cancel(self):
        self._event.set()

    def check(self):
        if self._event.is_set():
            raise Cancelled()


class ResourceMeter:
    """Single-context accounting. Owners explicitly retain/release reservations."""

    def __init__(self, policy: ResourcePolicy, phase: Phase,
                 cancellation: CancellationToken | None = None):
        self.policy = policy
        self.phase = phase
        self.cancellation = cancellation or CancellationToken()
        self._used: dict[str, int] = {}

    def used(self, key: str) -> int:
        return self._used.get(key, 0)

    def check(self, key: str, requested: int, *, file=None, span=None):
        self.cancellation.check()
        if type(requested) is not int or requested < 0:
            raise ValueError("resource counts must be nonnegative integers")
        limit = self.policy.limits[key]
        if key == "numeric_digits":
            limit = self.policy.decimal_digits
        if requested > limit:
            raise ResourceExceeded(key, limit, requested, self.phase, file, span)

    def reserve(self, *, file=None, span=None, **amounts: int) -> "Reservation":
        if len(amounts) == 1:
            # All fallible validation/arithmetic/owner allocation precedes the
            # single native-dict assignment. Multiple keys retain copy/commit.
            (key, amount), = amounts.items()
            if type(amount) is not int or amount < 0:
                raise ValueError("reservations must be nonnegative integers")
            requested = self.used(key) + amount
            self.check(key, requested, file=file, span=span)
            reservation = Reservation(self, amounts)
            self._used[key] = requested
            return reservation
        for key, amount in amounts.items():
            if type(amount) is not int or amount < 0:
                raise ValueError("reservations must be nonnegative integers")
            self.check(key, self.used(key) + amount, file=file, span=span)
        reservation = Reservation(self, amounts)
        updated = self._used.copy()
        for key, amount in amounts.items():
            updated[key] = self.used(key) + amount
        self._used = updated
        return reservation

    def consume(self, key: str, amount: int, *, file=None, span=None):
        # Cumulative source/output counters live until this context is discarded.
        self.reserve(file=file, span=span, **{key: amount})


class Reservation:
    __slots__ = ("_meter", "_amounts", "_released", "__weakref__")

    def __init__(self, meter: ResourceMeter, amounts: dict[str, int]):
        self._meter = meter
        self._amounts = amounts
        self._released = False

    def release(self):
        if not self._released:
            for key, amount in self._amounts.items():
                self._meter._used[key] -= amount
            self._released = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()
