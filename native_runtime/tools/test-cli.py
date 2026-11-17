"""N1 CLI resource/configuration boundaries, checked without a backend oracle."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): parser.error('do not overwrite evidence')
    exe=args.exe.resolve();records=[]
    with tempfile.TemporaryDirectory(prefix='ZZY N1 CLI 中文 ') as temporary:
        folder=Path(temporary);source=folder/'程序.zzy';config=folder/'limits.json'
        def run(name,arguments,status=0,stdout=None,code=None,key=None,tokens=None):
            command=[str(exe),*arguments]
            item=dict(id=name,command=command,expected_exit=status,passed=False)
            try:
                process=subprocess.run(command,cwd=folder,env=dict(os.environ,PATH='',PYTHONPATH='unusable'),capture_output=True,timeout=15)
                item.update(exit_code=process.returncode,stdout=process.stdout.decode('utf-8'),stderr=process.stderr.decode('utf-8'),timed_out=False)
                assert process.returncode==status,'exit code'
                if stdout is not None: assert item['stdout']==stdout,'stdout'
                if tokens is not None: assert [json.loads(line) for line in item['stdout'].splitlines()]==tokens,'fixed token records'
                if code:
                    d=json.loads(item['stderr'])
                    assert set(d)=={'schema_version','kind','code','file','span','message','notes'},'diagnostic fields'
                    assert d['schema_version']==1 and d['code']==code and d['kind']=='error','diagnostic schema/code'
                    if key: assert key in d['message'],'resource key'
                    assert len(process.stderr)<=4096,'diagnostic reserve'
                else: assert item['stderr']=='','unexpected stderr'
                item['passed']=True
            except (AssertionError,ValueError,subprocess.TimeoutExpired) as error: item['failure']=str(error)
            records.append(item)
            return item
        def limits(changes):
            config.write_text(json.dumps({'policy_version':1,'limits':changes}),encoding='utf-8')
        def lexargs(): return ['lex',str(source),'--limits',str(config),'--diagnostic-format=json']
        # Independent complete record constants, not output obtained from the executable.
        ident={'schema_version':1,'kind':'IDENT','lexeme':'a','value':None,'raw':False,'span':{'start':{'line':1,'column':1},'end':{'line':1,'column':2}}}
        eof={'schema_version':1,'kind':'EOF','lexeme':'','value':None,'raw':False,'span':{'start':{'line':1,'column':2},'end':{'line':1,'column':2}}}
        first=json.dumps(ident,ensure_ascii=False,separators=(',',':'))+'\n'
        whole=first+json.dumps(eof,ensure_ascii=False,separators=(',',':'))+'\n'
        source.write_bytes(b'a')
        for amount in [len(first.encode())-1,len(first.encode()),len(whole.encode())-1,len(whole.encode()),len(whole.encode())+1]:
            limits({'stdout_bytes':amount})
            good=amount>=len(whole.encode())
            run('stdout-boundary-'+str(amount),lexargs(),0 if good else 2,whole if good else first if amount>=len(first.encode()) else '',None if good else 'E211',None if good else 'stdout_bytes')
        limits({'stderr_bytes':1,'stdout_bytes':1});source.write_bytes(b'#')
        run('final-stderr-reserve',lexargs(),2,'','E211','stderr_bytes')
        source.write_bytes(b'abc')
        for size in [2,3,4]:
            limits({'source_file_bytes':3});source.write_bytes(b' '*size)
            run('file-cap-'+str(size),['source-info',str(source),'--limits',str(config),'--diagnostic-format','json'],0 if size<=3 else 2,None if size<=3 else '',None if size<=3 else 'E211','source_file_bytes' if size>3 else None)
        # Default 2 MiB file limit with adjacent bytes, through real file I/O.
        config.write_text('{"policy_version":1,"limits":{}}',encoding='utf-8')
        for size in [2097151,2097152,2097153]:
            source.write_bytes(b' '*size)
            item=run('default-file-cap-'+str(size),['source-info',str(source),'--diagnostic-format','json'],0 if size<=2097152 else 2,None if size<=2097152 else '',None if size<=2097152 else 'E211','source_file_bytes' if size>2097152 else None)
            if item['passed'] and size<=2097152:
                result=json.loads(item['stdout'])
                if (result['bytes'],result['codepoints'],result['lines'],result['sha256'])!=(size,size,1,hashlib.sha256(b' '*size).hexdigest()):
                    item.update(passed=False,failure='independent source-info size/hash')
        invalid=[b'',b'{}',b'[]',b'{"policy_version":true,"limits":{}}',b'{"policy_version":1,"limits":{"numeric_digits":false}}',b'{"policy_version":1,"limits":{"numeric_digits":null}}',b'{"policy_version":1,"limits":{"numeric_digits":0}}',b'{"policy_version":1,"limits":{"numeric_digits":-1}}',b'{"policy_version":1,"limits":{"numeric_digits":1.0}}',b'{"policy_version":1,"limits":{"numeric_digits":1e2}}',b'{"policy_version":1,"limits":{"numeric_digits":NaN}}',b'{"policy_version":1,"limits":{"numeric_digits":9223372036854775808}}',b'{"policy_version":1,"limits":{"numeric_digits":2,"numeric_\\u0064igits":3}}',b'{"policy_version":1,"limits":{},"policy_version":1}',b'{"policy_version":1,"limits":{},"extra":1}',b'{"policy_version":1,"limits":{"unknown":1}}',b'{"policy_version":1,"limits":{}}#',b'\xef\xbb\xbf{"policy_version":1,"limits":{}}',b'\xff',b'{"policy_version":1,"limits":{"\\ud800":1}}']
        for i,data in enumerate(invalid):
            config.write_bytes(data)
            run('invalid-config-'+str(i),['info','--limits',str(config),'--diagnostic-format','json'],2,'','E401')
        base=b'{"policy_version":1,"limits":{}}'
        for size in [65535,65536,65537]:
            config.write_bytes(base+b' '*(size-len(base)))
            run('config-size-'+str(size),['--limits',str(config),'info','--diagnostic-format=json'],0 if size<=65536 else 2,None if size<=65536 else '',None if size<=65536 else 'E401')
        limits({'numeric_digits':7})
        policy=json.loads((ROOT/'native_runtime/tests/inventory.json').read_text(encoding='utf-8'))['resource_policy']
        policy['limits']['numeric_digits']=7;policy['host_decimal_digits']=0;policy['effective_decimal_digits']=7
        fingerprint=hashlib.sha256(json.dumps(policy,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        item=run('dynamic-policy-fingerprint',['--diagnostic-format','json','--limits='+str(config),'info'])
        if item['passed']:
            actual=json.loads(item['stdout'])
            if actual['resource_policy']!=policy or actual['resource_fingerprint']!=fingerprint: item.update(passed=False,failure='independent policy canonicalization')
        for arguments in [['unknown'],['lex'],['source-info'],['lex','a','b'],['info','--bogus'],['--limits'],['--diagnostic-format'],['info','--diagnostic-format','bad'],['--lim','x','info']]:
            run('arguments-'+str(len(records)),arguments+['--diagnostic-format','json'],2,'','E401')
        for command in ['--help','--version']:
            run('bypass-config-'+command,[command,'--limits',str(folder/'missing.json')])
        run('help-subcommand',['lex','--help','--limits',str(folder/'missing.json')])
        run('missing-file',['source-info',str(folder/'missing.zzy'),'--diagnostic-format','json'],2,'','E401')
        run('directory-source',['lex',str(folder),'--diagnostic-format','json'],2,'','E401')
        # A lexically valid program that would write a file and print if executed.
        source.write_text('io.print("UNEXPECTED"); data.save_text("side-effect.txt", "bad");',encoding='utf-8')
        run('source-info-no-effects',['source-info',str(source)])
        run('lex-no-effects',['lex',str(source)])
        for command in ['check','run','test']:
            run('unsupported-'+command,[command,str(source),'--diagnostic-format','json'],2,'','E402')
        assert not (folder/'side-effect.txt').exists(),'user code executed'
        # Stop-option marker permits a filename which resembles a flag.
        (folder/'--help').write_bytes(b'a')
        run('end-options',['lex','--diagnostic-format','json','--','--help'],tokens=[ident,eof])
        for i in range(3):
            source.write_bytes(b'#');run('failure-recovery-error-'+str(i),['lex',str(source),'--diagnostic-format','json'],2,'','E101')
            source.write_bytes(b'a');run('failure-recovery-success-'+str(i),['lex',str(source),'--diagnostic-format','json'],stdout=whole)
    report=dict(schema_version=1,scope='N1 CLI configuration, output, source and no-execution boundaries',exe=str(exe),exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),count=len(records),passed=sum(r['passed'] for r in records),records=records)
    args.output.parent.mkdir(exist_ok=True,parents=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['count','passed','exe_sha256']}))
    for r in records:
        if not r['passed']: print(r['id'],r['failure'],r.get('stderr','')[:120])
    return 0 if records and all(r['passed'] for r in records) else 1

if __name__=='__main__': raise SystemExit(main())
