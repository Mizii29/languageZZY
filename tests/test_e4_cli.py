from tests.blackbox import ROOT, suite

def load_tests(loader, tests, pattern):
    return suite(ROOT / "tests/e4/cases.json")
