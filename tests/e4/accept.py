"""Consolidate completed evidence; this does not run or replace any test."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess

from zzy.native.sketch_metadata import ABI,FUNCTIONS
from zzy.native.sketch import LIMITS

ROOT=Path(__file__).resolve().parents[2]


def main():
    def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))
    files={'all':'tests/e4/results/all-tests.json','gui':'tests/e4/results/gui.json',
           'installed':'tests/e4/results/installed.json','cli':'tests/e4/results/cli.json',
           'baseline':'benchmarks/sketch/results/baseline.json','render':'benchmarks/sketch/results/render.json',
           'seek':'benchmarks/sketch/results/seek-final.json'}
    reports={key:read(path) for key,path in files.items()}
    for key in ('all','gui'):
        report=reports[key]
        assert report['passed'] and report['collected']==report['tests_run']>0
        assert all(report[k]==0 for k in ('failures','errors','skipped','expected_failures'))
    assert reports['gui']['tests_run']>=11 and reports['cli']['passed'] and reports['cli']['tests_run']>=26
    assert reports['installed']['passed'] and reports['installed']['probe']['passed']
    for key in ('baseline','render','seek'):assert reports[key]['driver_passed'] and reports[key]['samples']
    assert reports['baseline']['equivalent_pairs']==reports['baseline']['expected_pairs']==27
    for key in ('render','seek'):
        for name,sha in reports[key]['runtime_hashes'].items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,(key,name)
    frozen=read('tests/e4/results/tested-source.json')
    for name,sha in frozen['hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    for entry in reports['installed']['source_files']:
        text=(ROOT/'zzy'/entry['path']).read_text(encoding='utf-8')
        assert hashlib.sha256(text.encode()).hexdigest()==entry['text_sha256'],entry['path']
    requirement=hashlib.sha256((ROOT/'docs/requirement.md').read_bytes()).hexdigest()
    assert requirement=='b099c19fc339ce1dc1aab7e9d6c8126a9c5c9ace3d31b969a0623df90f521d2b'
    assert ABI=='1.0' and len(FUNCTIONS)==66
    report=dict(completed_at=datetime.now(timezone.utc).isoformat(),complete_sketch_1_0=True,extension_abi=ABI,
                function_count=len(FUNCTIONS),completed_tasks=['E1-01','E1-02','E2-01','E3-01','E3-02','E4-01','E4-02'],
                next_task='P11-01',base_revision='ac91a27c13c154a159c06b3fb2fac57a96ff2cf1',baseline_revision='a977596',
                pre_acceptance_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                capabilities=dict(core=True,headless=True,svg=True,history=True,patterns=True,projects=True,
                    gui='verified Windows 11 CPython 3.12.14 Tk 8.6.12; explicit --gui',png=False),
                extension_limits=dict(LIMITS),requirement_sha256=requirement,
                evidence={key:dict(path=path,sha256=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()) for key,path in files.items()},
                all_tests=reports['all'],gui_tests=reports['gui'],
                benchmark_statuses={key:{status:sum(s['status']==status for s in reports[key]['samples'])
                    for status in {s['status'] for s in reports[key]['samples']}} for key in ('baseline','render','seek')},
                unverified=['other OS/Python/fonts/DPI','all simultaneous maximum resource combinations','real OS ACL failures',
                    'power-loss durability and concurrent writer transactions','every blocking host call cancellation timing'],
                unavailable=['independent PNG renderer'])
    (ROOT/'tests/e4/results/acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(complete_sketch_1_0=True,all_tests=reports['all']['tests_run'],gui_tests=reports['gui']['tests_run'],next_task='P11-01')))


if __name__=='__main__':main()
