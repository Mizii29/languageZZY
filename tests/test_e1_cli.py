"""E1 fixed external CLI expectations."""
from tests.blackbox import ROOT, suite

def load_tests(loader, tests, pattern):
    return suite(ROOT / "tests/e1/cases.json")
