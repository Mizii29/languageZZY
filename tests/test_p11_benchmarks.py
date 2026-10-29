import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from benchmarks.p11 import workloads, statistics_rows
from benchmarks.p11_reference import CheckedStats


class P11BenchmarkTests(unittest.TestCase):
    def test_manifest_and_reference_fixed_answers(self):
        jobs=workloads()
        self.assertEqual(len({(j['case'],j['n']) for j in jobs}),len(jobs))
        self.assertEqual({j['case'] for j in jobs if j['case'].startswith('B')},{f'B{i:02}' for i in range(1,10)})
        for values,answer in [([],[0,0,None,None]),([3],[1,3,3,3]),([2,2,1],[3,5,1,2])]:
            checked=CheckedStats(values)
            try:self.assertEqual(checked.stats(),answer)
            finally:checked.close()
            self.assertTrue(all(v==0 for v in checked.meter._used.values()))
        for values in ([1,True],[1,'x']):
            checked=CheckedStats(values)
            try:
                with self.assertRaises(TypeError):checked.stats()
            finally:checked.close()

    def test_statistics_preserve_failed_and_missing_samples(self):
        rows=[dict(variant='before',case='B01',n=1,scope='cli',phase='sample',status='ok',wall_ns=n) for n in (10,20,30)]
        rows.append(dict(variant='before',case='B01',n=1,scope='cli',phase='sample',status='failure'))
        result=statistics_rows(rows)[0]
        self.assertEqual((result['count'],result['median'],result['MAD']),(3,20,10))
        self.assertEqual(len(rows),4)
        self.assertEqual(statistics_rows([]),[])

    def test_real_snapshot_precheck(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'results'
            command=[sys.executable,'-X','utf8','-m','benchmarks.p11','--verify-only','--before','HEAD','--after','WORKTREE','--cases','B01','S01','Q01','D02','K01','--output',str(output)]
            result=subprocess.run(command,capture_output=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stderr.decode())
            report=json.loads((output/'summary.json').read_bytes())
            self.assertTrue(report['passed']);self.assertGreater(report['records'],0)
            self.assertEqual(report['failures'],[])


if __name__=='__main__':unittest.main()
