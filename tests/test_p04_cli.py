"""Independent P04 CLI fixtures and external expected outputs."""
from tests.blackbox import ROOT, suite

def load_tests(loader, standard_tests, pattern):
    return suite(ROOT / "tests/p04/cases.json")
