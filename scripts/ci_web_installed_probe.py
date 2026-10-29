"""Run the optional HTTP/schema suite against an installed wheel outside the checkout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    report=args.report.resolve()
    if report.exists():parser.error('report already exists')
    import zzy
    package=Path(zzy.__file__).resolve().parent
    if package == root/'zzy' or not package.is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError('must use an installed wheel and Python -I')
    names={p.relative_to(root/'zzy').as_posix() for p in (root/'zzy').rglob('*.py')}
    if names!={p.relative_to(package).as_posix() for p in package.rglob('*.py')}:
        raise RuntimeError('installed source inventory differs')
    for name in names:
        if (root/'zzy'/name).read_text(encoding='utf-8')!=(package/name).read_text(encoding='utf-8'):
            raise RuntimeError('installed source differs: '+name)
    with tempfile.TemporaryDirectory(prefix='zzy installed HTTP ') as directory:
        work=Path(directory)
        (work/'tests/p08').mkdir(parents=True)
        for name in ('__init__.py','__main__.py','web_http.py','schema_contracts.py','test_contracts.py'):
            shutil.copy2(root/'tests'/name,work/'tests'/name)
        for name in ('edge.zzy','shared.zzy'):
            shutil.copy2(root/'tests/p08'/name,work/'tests/p08'/name)
        for folder in ('web','sqlite','contracts'):
            target=work/'examples'/folder;target.mkdir(parents=True)
            for source in (root/'examples'/folder).iterdir():
                if source.suffix in {'.zzy','.json','.html'}:shutil.copy2(source,target/source.name)
        probe=work/'probe.py'
        probe.write_text('import pathlib,sys\n'
                         'sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))\n'
                         'from tests.web_http import main\n'
                         'raise SystemExit(main())\n',encoding='utf-8')
        command=[sys.executable,'-I','-X','utf8',str(probe),'--report',str(work/'http.json')]
        env=dict(os.environ);env.pop('PYTHONPATH',None)
        result=subprocess.run(command,cwd=work,env=env,capture_output=True,timeout=120)
        print(result.stdout.decode('utf-8'),end='')
        print(result.stderr.decode('utf-8'),end='',file=sys.stderr)
        if result.returncode:raise RuntimeError('installed HTTP suite failed')
        data=json.loads((work/'http.json').read_bytes())
        if not data['passed'] or data['tests_run']!=data['collected'] or data['collected']<=0 or any(data[k] for k in ('failures','errors','skipped','expected_failures')):
            raise RuntimeError('installed HTTP report incomplete')
        data.update(installed_package=str(package),source_files=len(names),command=command,
                    source_sha256={name:hashlib.sha256((package/name).read_bytes()).hexdigest() for name in sorted(names)})
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
