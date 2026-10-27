"""CI must reject false success, stale evidence and silently removed tests."""
import copy
from unittest.mock import patch
import unittest

from scripts import ci


def successful_suite():
    return dict(passed=True, collected=2, tests_run=2, failures=0, errors=0, skipped=0, expected_failures=0)


class CIGateTests(unittest.TestCase):
    def setUp(self):
        self.context = dict(checkout_sha='candidate', run_id='123', attempt='1', source_fingerprint='source')
        self.reports = {kind: dict(kind=kind, passed=True, context=dict(self.context))
                        for kind in ('static', 'regression', 'package')}
        self.reports['static']['inventory'] = dict(collected=2)
        self.reports['regression']['suite'] = successful_suite()
        self.reports['package']['probe'] = dict(passed=True)

    def test_accepts_complete_matching_evidence(self):
        ci.validate_gate(self.reports, self.context)

    def test_rejects_prior_run_attempt_commit_and_source(self):
        for key in self.context:
            with self.subTest(key=key):
                reports = copy.deepcopy(self.reports)
                reports['package']['context'][key] = 'stale'
                with self.assertRaises(ValueError): ci.validate_gate(reports, self.context)

    def test_rejects_failed_or_wrong_kind_job(self):
        for kind in self.reports:
            for field, value in [('passed', False), ('kind', 'other')]:
                with self.subTest(kind=kind, field=field):
                    reports = copy.deepcopy(self.reports); reports[kind][field] = value
                    with self.assertRaises(ValueError): ci.validate_gate(reports, self.context)

    def test_rejects_missing_install_proof(self):
        del self.reports['package']['probe']
        with self.assertRaises(ValueError): ci.validate_gate(self.reports, self.context)

    def test_rejects_zero_partial_skipped_or_expected_failure_suite(self):
        for key, value in [('collected', 0), ('tests_run', 1), ('skipped', 1),
                           ('expected_failures', 1), ('failures', 1), ('errors', 1), ('passed', False)]:
            with self.subTest(key=key):
                report = successful_suite(); report[key] = value
                with self.assertRaises(ValueError): ci.validate_suite(report, 2)

    def test_rejects_missing_report_fields(self):
        for key in successful_suite():
            with self.subTest(key=key):
                report = successful_suite(); del report[key]
                with self.assertRaises(ValueError): ci.validate_suite(report, 2)

    def test_inventory_allows_additions(self):
        ci.check_inventory(dict(test_ids=['a', 'b'], manifests={'m': ['x', 'y']}),
                           dict(test_ids=['a'], manifests={'m': ['x']}))

    def test_inventory_preserves_repeated_policy_regressions(self):
        with self.assertRaises(ValueError):
            ci.check_inventory(dict(test_ids=['same'], manifests={}),
                               dict(test_ids=['same', 'same'], manifests={}))

    def test_intentional_missing_file_is_distinct_from_lost_fixture(self):
        case = dict(cwd='tests', file='missing.zzy', exit_code=2,
                    diagnostic=dict(code='E401', span=None))
        with patch('pathlib.Path.is_file', return_value=False):
            ci.check_fixture(case)
            for change in [dict(exit_code=0), dict(diagnostic=dict(code='E302', span=None))]:
                with self.subTest(change=change), self.assertRaises(ValueError):
                    ci.check_fixture(dict(case, **change))

    def test_inventory_rejects_removed_tests_and_manifest_cases(self):
        baseline = dict(test_ids=['a', 'b'], manifests={'m': ['x', 'y']})
        for current in [dict(test_ids=['a'], manifests={'m': ['x', 'y']}),
                        dict(test_ids=['a', 'b'], manifests={'m': ['x']}),
                        dict(test_ids=['a', 'b'], manifests={})]:
            with self.subTest(current=current):
                with self.assertRaises(ValueError): ci.check_inventory(current, baseline)


if __name__ == '__main__':
    unittest.main()
