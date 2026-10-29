"""Withdrawn P11-04 experiment, test-only; never installed or selected by ZZY.

The exact timed integrated interpreter is archived as tests/p11/04-candidate-interpreter.py.gz.
This subclass keeps its guarded arithmetic reproducible for semantic tests only;
its extra super() fallback is not the timed implementation.
"""
from zzy.interpreter import Interpreter
from zzy.values import Value


class SmallIntegerCandidate(Interpreter):
    def integer_operation(self, operation, left, right, node):
        if operation in {"PLUS", "MINUS"}:
            bits = self._small_add_sub_bits(operation, left, right, node)
            if bits is not None:
                self.check("integer_bits", bits, node)
                reservation = self.reserve(node, runtime_payload_bytes=(bits + 7) // 8)
                return Value("Int", left + right if operation == "PLUS" else left - right, reservation)
        return super().integer_operation(operation, left, right, node)

    def _small_add_sub_bits(self, operation, left, right, node):
        # Called only after binary/array's actual Int tag checks. Guard before
        # changing accounting; a conservative upper bound never rejects input.
        width = max(left.bit_length(), right.bit_length())
        if not 0 < width <= 30 or width % 8 == 0:
            return None
        if (left == -right if operation == "PLUS" else left == right):
            return None  # preserve the generic zero/cancellation shortcut
        upper = width + 1
        if (upper > self.meter.policy.limits["integer_bits"] or
                (upper + 7) // 8 > self.meter.policy.limits["runtime_payload_bytes"]
                - self.meter.used("runtime_payload_bytes")):
            return None
        scratch = (width + 7) // 8
        with self.reserve(node, runtime_payload_bytes=scratch):
            # Same one cancellation point per byte as add_bits/difference_bits.
            for _ in range(scratch):
                self.meter.cancellation.check()
            # Excluding byte-aligned widths makes this bounded temporary fit
            # the ORIGINAL scratch reservation, including a possible carry.
            return (left + right if operation == "PLUS" else left - right).bit_length()
