"""Fixed-answer checks for the P12 staged timing boundary."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from benchmarks.common import ROOT
from benchmarks.p12.run import expected, source
from benchmarks.p12.run_stages import wall_budget_exceeded
from zzy.process import run_bounded


class P12StageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='ZZY P12 stage ')
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)

    def command(self, args):
        return run_bounded([sys.executable, '-X', 'utf8', *args], cwd=ROOT,
                           env=dict(os.environ, PYTHONPATH=str(ROOT), PYTHONUTF8='1'),
                           timeout=30)

    def test_small_cli_and_staged_answers_match_independent_oracle(self):
        for case in ('X00', 'X01', 'X02', 'X03'):
            n = None if case == 'X00' else 5
            for language in ('zzy', 'python'):
                with self.subTest(case=case, language=language):
                    suffix = 'zzy' if language == 'zzy' else 'py'
                    path = self.directory/f'{case}-{n}.{suffix}'
                    path.write_bytes(source(case, n, language))
                    cli = (['-m', 'zzy', 'run', str(path)] if language == 'zzy'
                           else [str(path)])
                    code, out, err = self.command(cli)
                    self.assertEqual((code, err, out.decode('utf-8').splitlines()),
                                     (0, b'', [expected(case, n)]))
                    code, out, err = self.command(['-m', 'benchmarks.p12.stage_worker',
                        language, case, 'none' if n is None else str(n), str(path)])
                    self.assertEqual((code, err), (0, b''), out.decode('utf-8'))
                    record = json.loads(out)
                    self.assertEqual(record['status'], 'ok')
                    self.assertGreater(record['timings']['execute_ns'], 0)

    def test_batch_restarts_mutable_array_and_wrong_answer_is_rejected(self):
        path = self.directory/'X03-5.zzy'
        path.write_bytes(source('X03', 5, 'zzy'))
        code, out, err = self.command(['-m', 'benchmarks.p12.stage_worker',
                                      'zzy', 'X03', '5', str(path), '--batch', '3'])
        self.assertEqual((code, err), (0, b''), out.decode('utf-8'))
        self.assertEqual(json.loads(out)['batch'], 3)
        wrong = self.directory/'X01-wrong.py'
        wrong.write_text('def bench():\n    return 0\n', encoding='utf-8')
        code, out, err = self.command(['-m', 'benchmarks.p12.stage_worker',
                                      'python', 'X01', '5', str(wrong)])
        self.assertNotEqual(code, 0)
        self.assertEqual(err, b'')
        self.assertEqual(json.loads(out)['status'], 'error')

    def test_parent_wall_budget_catches_success_after_limit(self):
        self.assertFalse(wall_budget_exceeded(30_000_000_000))
        self.assertTrue(wall_budget_exceeded(30_000_000_001))


if __name__ == '__main__':
    unittest.main()
