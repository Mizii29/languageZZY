"""P03 language behavior through real CLI processes and external expectations."""
from tests.blackbox import ROOT, suite


def load_tests(loader, standard_tests, pattern):
    return suite(ROOT / "tests/p03/cases.json")
