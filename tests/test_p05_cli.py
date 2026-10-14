"""P05 behavior is checked through real processes and independent expectations."""
from tests.blackbox import ROOT, suite

def load_tests(loader, standard_tests, pattern):
    return suite(ROOT / 'tests/p05/cases.json')
