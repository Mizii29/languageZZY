from tests.blackbox import ROOT, suite

def load_tests(loader, tests, pattern):
    return suite(ROOT / "tests/e3/cases.json")
