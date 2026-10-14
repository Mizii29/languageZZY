"""Discover independent check expectations without executing user expressions."""

from tests.blackbox import ROOT, suite


def load_tests(loader, standard_tests, pattern):
    return suite(ROOT / "tests/check/cases.json")
