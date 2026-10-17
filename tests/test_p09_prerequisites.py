"""P09-01 prerequisite checks; this is not acceptance of the future application."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from tests import blackbox
from tests.blackbox import ROOT, load_cases
from zzy.process import run_bounded
from zzy.resources import ResourcePolicy


CONFIG = ROOT / 'apps/zzy-campus/limits.json'


class CampusPolicyTests(unittest.TestCase):
    def cli(self, cwd, *args):
        return run_bounded(
            [sys.executable, '-X', 'utf8', '-m', 'zzy', *map(str, args),
             '--limits', str(CONFIG), '--diagnostic-format', 'json'],
            cwd=cwd, env=dict(os.environ, PYTHONPATH=str(ROOT)), timeout=30)

    def test_actual_startup_policy_only_tightens_file_payload(self):
        policy = ResourcePolicy.from_file(CONFIG)
        expected = dict(ResourcePolicy().limits, io_payload_bytes=4 * 1024**2)
        self.assertEqual(dict(policy.limits), expected)
        status, out, err = self.cli(ROOT, 'info')
        self.assertEqual((status, err), (0, b''))
        record = json.loads(out)
        self.assertEqual(record['resource_policy'], policy.effective_record())
        self.assertEqual(record['resource_fingerprint'], policy.fingerprint)

    def test_file_read_rejects_bytes_above_four_mib(self):
        probe = ROOT / 'tests/p09/read-limit.zzy'
        with tempfile.TemporaryDirectory(prefix='ZZY campus 前置 ') as directory:
            cwd = Path(directory)
            for size in (4194303, 4194304, 4194305):
                with self.subTest(size=size):
                    (cwd / 'payload.txt').write_bytes(b'x' * size)
                    status, out, err = self.cli(cwd, 'run', probe)
                    if size <= 4194304:
                        self.assertEqual((status, out, err),
                                         (0, f'{size}\n'.encode(), b''))
                    else:
                        self.assertEqual((status, out), (1, b''))
                        diagnostic = json.loads(err)
                        self.assertEqual(diagnostic['code'], 'E211')
                        self.assertIn('io_payload_bytes', diagnostic['message'])
            # check must not try to read the missing file.
            (cwd / 'payload.txt').unlink()
            self.assertEqual(self.cli(cwd, 'check', probe), (0, b'', b''))


def load_tests(loader, standard_tests, pattern):
    manifest = json.loads((ROOT / 'tests/p09/prerequisites.json').read_text(encoding='utf-8'))
    entries = manifest['cases']
    if not entries:
        raise ValueError('empty prerequisite collection')
    seen = set()
    policy = ResourcePolicy.from_file(CONFIG)
    for entry in entries:
        identity = (entry['manifest'], entry['id'], entry['mode'])
        if identity in seen:
            raise ValueError('duplicate prerequisite')
        seen.add(identity)
        matches = [case for case in load_cases(ROOT / entry['manifest'])
                   if (case['id'], case['mode']) == (entry['id'], entry['mode'])]
        if len(matches) != 1:
            raise ValueError(f'missing/ambiguous prerequisite: {identity}')
        case = dict(matches[0])
        if case.get('limits'):
            raise ValueError('prerequisite must use the actual campus policy')
        case['limits'] = dict(policy.limits)
        standard_tests.addTest(blackbox.BlackboxCase(case))
    return standard_tests
