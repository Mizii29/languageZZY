from pathlib import Path
import unittest
from unittest.mock import patch

from zzy.diagnostics import Cancelled, Phase, ResourceExceeded
from zzy.lexer import Lexer, identifier_continue
from zzy.resources import CancellationToken, ResourceMeter, ResourcePolicy
from zzy.source import Source


def scan(text, policy=None, cancellation=None):
    return Lexer(Source.from_bytes(Path("probe.zzy"), text.encode("utf-8")),
                 ResourceMeter(policy or ResourcePolicy(), Phase.FRONTEND, cancellation)).scan()


class LexerResourceTests(unittest.TestCase):
    def test_default_token_limit_including_eof_exemption(self):
        limit = 250_000
        for count in (limit - 1, limit, limit + 1):
            with self.subTest(count=count):
                if count <= limit:
                    tokens = scan(";" * count)
                    self.assertEqual(len(tokens), count + 1)
                    self.assertEqual(tokens[-1].kind, "EOF")
                    del tokens
                else:
                    with self.assertRaises(ResourceExceeded) as caught:
                        scan(";" * count)
                    self.assertEqual(caught.exception.key, "tokens_per_file")
                    self.assertEqual(caught.exception.requested, limit + 1)

    def test_per_file_counts_do_not_accumulate(self):
        meter = ResourceMeter(ResourcePolicy({"tokens_per_file": 1}), Phase.FRONTEND)
        for name in ("a.zzy", "b.zzy"):
            self.assertEqual(len(Lexer(Source.from_bytes(Path(name), b"x"), meter).scan()), 2)

    def test_host_digit_limit_and_no_numeric_conversion(self):
        policy = ResourcePolicy(host_decimal_digits=640)
        tokens = scan("0" * 640 + "::s", policy)
        self.assertEqual(tokens[0].lexeme, "0" * 640)
        self.assertIsNone(tokens[0].value)
        with self.assertRaises(ResourceExceeded) as caught:
            scan("0" * 641, policy)
        self.assertEqual(caught.exception.limit, 640)

    def test_long_names_and_comment_candidates_use_linear_boundary_checks(self):
        for size in (10_000, 20_000):
            with patch("zzy.lexer.identifier_continue", wraps=identifier_continue) as boundary:
                self.assertEqual(scan("名" * size)[0].lexeme, "名" * size)
                self.assertLessEqual(boundary.call_count, size + 5)
            with patch("zzy.lexer.identifier_continue", wraps=identifier_continue) as boundary:
                text = "zzysayalot:" + " zzyending" * size + " zzyend"
                self.assertEqual([token.kind for token in scan(text)], ["EOF"])
                self.assertLessEqual(boundary.call_count, 2 * size + 5)

    def test_cancellation_during_each_long_scan(self):
        class CancelDuringScan(CancellationToken):
            def __init__(self):
                super().__init__()
                self.checks = 0

            def check(self):
                self.checks += 1
                if self.checks == 8:
                    self.cancel()
                super().check()

        for text in ("x" * 20000, "zzysay:" + "x" * 20000,
                     "zzysayalot:" + "x" * 20000, '"' + "x" * 20000 + '"'):
            with self.subTest(prefix=text[:12]), self.assertRaises(Cancelled):
                scan(text, cancellation=CancelDuringScan())
