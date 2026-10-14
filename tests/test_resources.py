import json
from pathlib import Path
import sys
import tempfile
import unittest

from zzy.diagnostics import Cancelled, DiagnosticError, Phase, ResourceExceeded
from zzy.resources import CancellationToken, DEFAULT_LIMITS, ResourceMeter, ResourcePolicy


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "limits.json"

    def load(self, text):
        self.path.write_text(text, encoding="utf-8")
        return ResourcePolicy.from_file(self.path)

    def test_defaults_and_fingerprint(self):
        default = ResourcePolicy()
        self.assertEqual(len(default.limits), 22)
        self.assertEqual(default.limits["source_total_bytes"], 16777216)
        self.assertEqual(default.limits["runtime_payload_bytes"], 134217728)
        first = self.load('{"policy_version":1,"limits":{"stdout_bytes":7,"call_depth":8}}')
        second = self.load('{"limits":{"call_depth":8,"stdout_bytes":7},"policy_version":1}')
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertNotEqual(first.fingerprint, default.fingerprint)
        self.assertEqual(len(first.fingerprint), 64)
        with self.assertRaises(TypeError):
            default.limits["call_depth"] = 1

    def test_host_decimal_limit(self):
        before = sys.get_int_max_str_digits()
        self.assertEqual(ResourcePolicy(host_decimal_digits=0).decimal_digits, 4096)
        self.assertEqual(ResourcePolicy(host_decimal_digits=640).decimal_digits, 640)
        self.assertNotEqual(ResourcePolicy(host_decimal_digits=0).fingerprint,
                            ResourcePolicy(host_decimal_digits=4300).fingerprint)
        self.assertEqual(sys.get_int_max_str_digits(), before)

    def test_reject_invalid_configuration(self):
        invalid = ["", "[]", "null", "{}", '{"policy_version":1}',
                   '{"policy_version":1,"limits":{},"unknown":1}',
                   '{"policy_version":1,"limits":{"call_depth":1,"call_depth":2}}',
                   '{"policy_version":1,"policy_version":1,"limits":{}}',
                   '{"policy_version":true,"limits":{}}',
                   '{"policy_version":2,"limits":{}}',
                   '{"policy_version":1,"limits":[]}',
                   '{"policy_version":1,"limits":{"unknown":1}}',
                   '{"policy_version":1,"limits":{"call_depth":' + "9" * 5000 + '}}',
                   "[" * 2000 + "]" * 2000]
        for value in (True, 0, -1, 2.0, "2 MiB", None, [], sys.maxsize + 1,
                      float("inf"), float("nan")):
            invalid.append(json.dumps({"policy_version": 1, "limits": {"call_depth": value}}))
        for text in invalid:
            with self.subTest(text=text[:100]), self.assertRaises(DiagnosticError) as caught:
                self.load(text)
            self.assertEqual(caught.exception.exit_code, 2)
            self.assertEqual(caught.exception.diagnostic.code, "E401")
            self.assertIsNone(caught.exception.diagnostic.span)

    def test_configuration_size_and_encoding(self):
        valid = '{"policy_version":1,"limits":{}}'
        for size in (65535, 65536):
            self.assertEqual(self.load(valid.ljust(size)).fingerprint, ResourcePolicy().fingerprint)
        with self.assertRaises(DiagnosticError):
            self.load(valid.ljust(65537))
        self.path.write_bytes(b"\xff")
        with self.assertRaises(DiagnosticError):
            ResourcePolicy.from_file(self.path)
        with self.assertRaises(DiagnosticError):
            ResourcePolicy.from_file(self.path.parent / "missing")

    def test_single_limit_may_exceed_total(self):
        policy = self.load('{"policy_version":1,"limits":{"source_file_bytes":10,"source_total_bytes":2}}')
        self.assertEqual(policy.limits["source_file_bytes"], 10)
        self.assertEqual(policy.limits["source_total_bytes"], 2)


class MeterTests(unittest.TestCase):
    def test_each_counter_boundary_and_phase(self):
        # Interface checks only; no claim that future AST/value allocation is implemented.
        for phase in Phase:
            meter = ResourceMeter(ResourcePolicy({key: 3 for key in DEFAULT_LIMITS}), phase)
            for key in DEFAULT_LIMITS:
                with self.subTest(phase=phase, key=key):
                    meter.check(key, 2)
                    meter.check(key, 3)
                    with self.assertRaises(ResourceExceeded) as caught:
                        meter.check(key, 4)
                    self.assertEqual(caught.exception.exit_code, phase.value)
                    self.assertIn(key, caught.exception.diagnostic.message)
                    self.assertEqual(caught.exception.limit, 3)
                    self.assertEqual(caught.exception.requested, 4)

    def test_reservation_atomicity_release_and_ownership(self):
        meter = ResourceMeter(ResourcePolicy({"runtime_objects": 2, "runtime_slots": 3}), Phase.EXECUTION)
        owner = meter.reserve(runtime_objects=1, runtime_slots=2)
        with self.assertRaises(ResourceExceeded):
            meter.reserve(runtime_objects=1, runtime_slots=2)
        self.assertEqual(meter.used("runtime_objects"), 1)
        self.assertEqual(meter.used("runtime_slots"), 2)
        with self.assertRaises(Cancelled):
            with meter.reserve(runtime_objects=1):
                raise Cancelled()
        self.assertEqual(meter.used("runtime_objects"), 1)
        owner.release()
        owner.release()
        self.assertEqual(meter.used("runtime_objects"), 0)
        self.assertEqual(meter.used("runtime_slots"), 0)

    def test_invalid_accounting_and_decimal_count(self):
        meter = ResourceMeter(ResourcePolicy(host_decimal_digits=640), Phase.EXECUTION)
        for value in (-1, True, 1.0):
            with self.assertRaises(ValueError):
                meter.reserve(runtime_slots=value)
        meter.check("numeric_digits", 640)
        with self.assertRaises(ResourceExceeded):
            meter.check("numeric_digits", 641)

    def test_cancel_escapes_native_exception_handler(self):
        token = CancellationToken()
        meter = ResourceMeter(ResourcePolicy(), Phase.EXECUTION, token)
        token.cancel()
        with self.assertRaises(Cancelled):
            try:
                meter.reserve(runtime_objects=1)
            except Exception:
                self.fail("context abort was caught as an ordinary error")
        self.assertEqual(meter.used("runtime_objects"), 0)
