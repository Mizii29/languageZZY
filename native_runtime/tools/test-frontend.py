"""Native subprocess verification against fixed external lex expectations (no Python ZZY oracle)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]

def check(condition,message):
    if not condition: raise AssertionError(message)

def span(value):
    return None if value is None else [value['start']['line'],value['start']['column'],value['end']['line'],value['end']['column']]

def run(exe,case,folder):
    command=[str(exe),case.get('mode','lex'),case['file'],'--diagnostic-format','json']
    if 'limits' in case:
        config=folder/'limits.json'
        config.write_text(json.dumps({'policy_version':1,'limits':case['limits']}),encoding='utf-8')
        command+=['--limits',str(config)]
    env=dict(os.environ,PATH='',PYTHONPATH='invalid-native-test-path',PYTHONIOENCODING='ascii')
    before=time.perf_counter()
    try:
        child=subprocess.run(command,cwd=ROOT/case.get('cwd','.'),env=env,input=b'',capture_output=True,timeout=case.get('timeout_seconds',10))
        record={'id':case['id'],'command':command,'exit_code':child.returncode,'stdout':child.stdout.decode('utf-8'),'stderr':child.stderr.decode('utf-8'),'timed_out':False,'seconds':time.perf_counter()-before}
    except subprocess.TimeoutExpired as error:
        return {'id':case['id'],'command':command,'timed_out':True,'passed':False,'failure':str(error)}
    try:
        check(record['exit_code']==case['exit_code'],'exit code differs')
        if 'tokens' in case:
            tokens=[json.loads(line) for line in record['stdout'].splitlines()]
            check(all(set(t)=={'schema_version','kind','lexeme','value','raw','span'} and type(t['schema_version']) is int and t['schema_version']==1 and type(t['raw']) is bool for t in tokens),'token record schema')
            actual=[[t['kind'],t['lexeme'],t['value'],t['raw'],span(t['span'])] for t in tokens]
            check(actual==case['tokens'],'fixed token expectation differs')
        elif 'info' in case:
            actual=json.loads(record['stdout'])
            check(actual==case['info'],'fixed source-info differs')
        else: check(record['stdout']==case.get('stdout',''),'stdout differs')
        if case['exit_code']==0: check(record['stderr']=='','unexpected stderr')
        else:
            diagnostic=json.loads(record['stderr'])
            check(set(diagnostic)=={'schema_version','kind','code','file','span','message','notes'},'diagnostic fields differ')
            check(diagnostic['schema_version']==1 and diagnostic['kind']=='error','diagnostic schema/kind differs')
            expected=case['diagnostic']
            check(diagnostic['code']==expected['code'] and span(diagnostic['span'])==expected['span'],'diagnostic code/span differs')
            expected_file=expected.get('file',os.path.relpath((ROOT/case['file']).resolve(),ROOT/case.get('cwd','.')).replace('\\','/'))
            check(diagnostic['file']==expected_file,'diagnostic file differs')
            check(expected.get('message_contains','') in diagnostic['message'],'diagnostic resource key differs')
            check(len(record['stderr'].encode())<=4096,'diagnostic reserve exceeded')
        record['passed']=True
    except (AssertionError,ValueError,KeyError,TypeError) as error:
        record['passed']=False;record['failure']=str(error)
    return record

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--exe',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    exe=args.exe.resolve()
    if args.output.exists(): parser.error('evidence already exists; choose a new output')
    cases=json.loads((ROOT/'tests/lex/cases.json').read_text(encoding='utf-8'))['cases']
    if not cases: parser.error('no fixed cases collected')
    records=[]
    with tempfile.TemporaryDirectory(prefix='ZZY native N1 中文 ') as temp:
        folder=Path(temp)
        for case in cases: records.append(run(exe,case,folder))
    report={'schema_version':1,'scope':'N1 native CLI against unchanged independent tests/lex/cases.json','exe':str(exe),'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'manifest_sha256':hashlib.sha256((ROOT/'tests/lex/cases.json').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'python_role':'development test coordinator only; native child PATH empty; no Python oracle','count':len(records),'passed':sum(r['passed'] for r in records),'records':records}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['count','passed','exe_sha256']}))
    for r in records:
        if not r['passed']: print(r['id'],r['failure'],r.get('stderr','')[:200])
    return 0 if records and all(r['passed'] for r in records) else 1

if __name__=='__main__': raise SystemExit(main())
