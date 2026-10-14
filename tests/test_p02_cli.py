"""P02 external programs, including non-executing check counterparts."""
from tests.blackbox import ROOT, suite


def load_tests(loader, standard_tests, pattern):
    return suite(ROOT / "tests/p02/cases.json")
