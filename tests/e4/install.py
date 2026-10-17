"""Build offline, install into a fresh venv, and run the real desktop probe.

Requires an existing Python with pip/setuptools via --installer. Downloads are
disabled. Keeps the isolated environment under ignored dist for inspection.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--installer',type=Path,required=True);args=parser.parse_args()
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    isolated=Path(tempfile.mkdtemp(prefix='E4 离线验收 ',dir=dist))
    work=isolated/'中文 空格 工作目录';work.mkdir()
    report=dict(started=datetime.now(timezone.utc).isoformat(),isolated=str(isolated),commands=[],passed=False)
    destination=ROOT/'tests/e4/results/installed.json'
    def save():destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def execute(command,cwd=ROOT,timeout=120):
        result=subprocess.run([str(x) for x in command],cwd=cwd,capture_output=True,timeout=timeout)
        record=dict(command=[str(x) for x in command],cwd=str(cwd),exit_code=result.returncode,
                    stdout=result.stdout.decode('utf-8',errors='replace'),stderr=result.stderr.decode('utf-8',errors='replace'))
        report['commands'].append(record);save()
        if result.returncode:raise RuntimeError(record)
        return record['stdout'].strip()
    execute([args.installer,'-X','utf8','-m','pip','wheel','.', '--no-deps','--no-build-isolation','--no-index','--no-cache-dir','--wheel-dir',dist])
    wheel=dist/'zzy_language-0.6.0a1-py3-none-any.whl'
    report['wheel_sha256']=hashlib.sha256(wheel.read_bytes()).hexdigest()
    env=isolated/'环境';venv.EnvBuilder(with_pip=False).create(env)
    python=env/'Scripts/python.exe'
    for target in (python,Path(sys.executable)):
        execute([args.installer,'-X','utf8','-m','pip','--python',target,'install','--force-reinstall','--no-index','--no-deps',wheel])
    package=Path(execute([python,'-I','-X','utf8','-c','import zzy;print(zzy.__file__)'],work)).parent
    report['source_files']=[]
    sources={str(p.relative_to(ROOT/'zzy')):p for p in (ROOT/'zzy').rglob('*.py')}
    installed={str(p.relative_to(package)):p for p in package.rglob('*.py')}
    assert sources.keys()==installed.keys()
    for name,p in sources.items():
        original=p.read_text(encoding='utf-8');copy=installed[name].read_text(encoding='utf-8')
        assert original==copy,name
        report['source_files'].append(dict(path=name,text_sha256=hashlib.sha256(original.encode()).hexdigest(),source_bytes_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),installed_bytes_sha256=hashlib.sha256(installed[name].read_bytes()).hexdigest()))
    shutil.copyfile(ROOT/'tests/e4/installed_probe.py',work/'installed_probe.py')
    shutil.copyfile(ROOT/'examples/sketch/studio.zzy',work/'studio.zzy')
    execute([python,'-I','-X','utf8','installed_probe.py'],work)
    report['probe']=json.loads((work/'installed-result.json').read_text(encoding='utf-8'))
    assert report['probe']['passed']
    report.update(passed=True,finished=datetime.now(timezone.utc).isoformat())
    save()
    print(json.dumps(dict(passed=True,source_files=len(sources),wheel_sha256=report['wheel_sha256'],report=str(destination)),ensure_ascii=False))


if __name__=='__main__':main()
