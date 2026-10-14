"""Discover the lex CLI cases through the common external-manifest runner."""

from tests.blackbox import ROOT, suite


def load_tests(loader, standard_tests, pattern):
    return suite(ROOT / "tests/lex/cases.json")
