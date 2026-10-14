"""P06 exact external CLI expectations."""
from tests.blackbox import ROOT, suite


def load_tests(loader, tests, pattern):
    return suite(ROOT / "tests/p06/cases.json")
