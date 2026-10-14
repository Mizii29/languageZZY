"""Validate pairs, then collect serial, seeded interleaved independent samples."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import gc
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
from time import perf_counter_ns
import unicodedata

from benchmarks.common import BASE, ROOT, POLICY, digest, expected_stdout, load_manifest, source
from zzy import __version__
from zzy.process import run_bounded


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT).decode('utf-8').strip()


def environment():
    machine = {}
    if os.name == 'nt':
        # Read-only system inventory; no shell interpolation or user documents.
        inventory = subprocess.run(['powershell','-NoProfile','-Command',
            '$c=Get-CimInstance Win32_Processor; $m=Get-CimInstance Win32_ComputerSystem; '
            '@{cpu=$c.Name; logical_processors=$m.NumberOfLogicalProcessors; memory_bytes=$m.TotalPhysicalMemory} | ConvertTo-Json -Compress'],
            capture_output=True,text=True,timeout=30)
        machine = json.loads(inventory.stdout) if inventory.returncode==0 else {'inventory_error':inventory.stderr}
        if not all(machine.get(key) for key in ('cpu','logical_processors','memory_bytes')):
            import ctypes
            import winreg
            class Memory(ctypes.Structure):
                _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong),
                    *[(key,ctypes.c_ulonglong) for key in ('total_physical','available_physical',
                      'total_page','available_page','total_virtual','available_virtual','available_extended')]]
            memory=Memory()
            memory.length=ctypes.sizeof(memory)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
                raise ctypes.WinError()
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
                cpu=winreg.QueryValueEx(key,'ProcessorNameString')[0]
            machine=dict(cpu=cpu,logical_processors=os.cpu_count(),memory_bytes=memory.total_physical,
                         source='Windows registry and GlobalMemoryStatusEx; CIM unavailable')
    return dict(timestamp=datetime.now(timezone.utc).isoformat(),python=sys.version,
        implementation=platform.python_implementation(),executable=sys.executable,
        unicode=unicodedata.unidata_version,os=platform.platform(),machine=machine,
        zzy_version=__version__,syntax_version='0.6',stdlib_version='0.6.1',
        installed_dependencies=sorted(f'{d.metadata["Name"]}=={d.version}' for d in importlib.metadata.distributions()),
        revision=git('rev-parse','HEAD'),git_status=git('status','--short'),
        gc_enabled=gc.isenabled(),gc_thresholds=gc.get_threshold(),
        timer=dict(name='time.perf_counter_ns',implementation=__import__('time').get_clock_info('perf_counter').implementation,
                   resolution_seconds=__import__('time').get_clock_info('perf_counter').resolution),
        resource_policy=POLICY.effective_record(),resource_fingerprint=POLICY.fingerprint,
        extensions=[],cache='no Program cache; fresh child per sample; OS page cache uncontrolled, not cold disk',
        tracked_runtime_hashes={str(p.relative_to(ROOT)).replace('\\','/'):digest(p.read_bytes()) for p in sorted((ROOT/'zzy').rglob('*.py'))})


def command(language,scope,case_id,n,path,batch):
    head = [sys.executable,'-X','utf8']
    if scope=='stages':
        return head+['-m','benchmarks.worker',language,case_id,str(n),str(path),'--batch',str(batch)]
    return head+(['-m','zzy','run',str(path),'--diagnostic-format','json'] if language=='zzy' else [str(path)])


def collect(language,scope,case_id,n,path,batch=1,timeout=30):
    cmd = command(language,scope,case_id,n,path,batch)
    row = dict(language=language,scope=scope,case=case_id,n=n,batch=batch,command=cmd,
               timeout_seconds=timeout,resource_fingerprint=POLICY.fingerprint)
    started = perf_counter_ns()
    try:
        status,stdout,stderr = run_bounded(cmd,cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT),PYTHONUTF8='1'),
                                           timeout=timeout,output_limit=1024**2+4096)
        elapsed = perf_counter_ns()-started
        if scope=='stages':
            result = json.loads(stdout)
            if stderr or (status==0) != (result.get('status')=='ok'):
                raise AssertionError('worker exit/output mismatch')
            row.update(result)
        elif status != 0:
            row.update(status='resource_failure' if b'"E211"' in stderr else 'cli_failure',
                       exit_code=status,stderr=stderr.decode('utf-8',errors='replace'),result_check=False)
        elif stderr or stdout != (expected_stdout(case_id,n).replace(b'\n',os.linesep.encode()) if language=='python' else expected_stdout(case_id,n)):
            row.update(status='wrong_result',exit_code=status,result_check=False,
                       stdout_sha256=digest(stdout),stderr=stderr.decode('utf-8',errors='replace'))
        else:
            row.update(status='ok',result_check=True,exit_code=0,stdout_sha256=digest(stdout),elapsed_ns=elapsed)
        row['parent_elapsed_ns'] = elapsed
    except subprocess.TimeoutExpired:
        row.update(status='timeout',result_check=False,parent_elapsed_ns=perf_counter_ns()-started)
    except Exception as error:
        row.update(status='error',result_check=False,error=f'{type(error).__name__}: {error}',
                   parent_elapsed_ns=perf_counter_ns()-started)
    return row


def summarize(rows):
    grouped = defaultdict(list)
    failures = []
    for row in rows:
        if row['status'] != 'ok':
            failures.append(row)
        if row.get('phase') != 'sample' or row['status'] != 'ok':
            continue
        group = (row['case'],row['n'],row['language'])
        if row['scope']=='cli_total':
            grouped[(*group,'cli_total')].append(row['elapsed_ns'])
        else:
            for key,value in row['timings'].items():
                grouped[(*group,key.removesuffix('_ns'))].append(value/(1 if key in {'read_ns','prepare_ns'} else row['batch']))
            for key,value in row.get('frontend_probe',{}).items():
                if key.endswith('_ns'):
                    grouped[(*group,'probe_'+key[:-3])].append(value)
    statistics_rows = []
    for (case,n,language,scope),values in sorted(grouped.items()):
        median = statistics.median(values)
        statistics_rows.append(dict(case=case,n=n,language=language,scope=scope,samples=len(values),
            median_ns=median,min_ns=min(values),max_ns=max(values),
            mad_ns=statistics.median(abs(v-median) for v in values)))
    return dict(statistics=statistics_rows,failures=failures,total_records=len(rows))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--verify-only',action='store_true')
    parser.add_argument('--cases',nargs='+')
    args = parser.parse_args(argv)
    manifest = load_manifest()
    cases = [c for c in manifest['cases'] if args.cases is None or c['id'] in args.cases]
    if not cases or args.cases is not None and set(args.cases)!={c['id'] for c in cases}:
        raise ValueError('empty or unknown case selection')
    # Refuse accidental overwrite of baseline evidence.
    args.output.mkdir(parents=True,exist_ok=False)
    meta = environment()
    meta.update(order_seed=manifest['order_seed'],warmups=3,samples=15,
                batch_policy='target 100ms execute; ceil(100ms/preflight execute), cap 1000; total setup+execute target capped at 5s; fresh initial state each iteration',
                selected_cases=[c['id'] for c in cases],verify_only=args.verify_only)
    meta['environment_id'] = digest(json.dumps(meta,sort_keys=True).encode())
    (args.output/'environment.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (args.output/'tracked.diff').write_text(git('diff','HEAD','--'),encoding='utf-8')
    (args.output/'cases.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    inputs = args.output/'inputs'
    inputs.mkdir()
    rows,paths = [],{}
    with (args.output/'raw.jsonl').open('w',encoding='utf-8') as stream:
        def save(row,phase,index):
            row.update(phase=phase,sample_index=index,order_index=len(rows),environment_id=meta['environment_id'])
            rows.append(row)
            stream.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
            stream.flush()
        jobs=[]
        for case in cases:
            sizes=([1,2,10] if case['id']=='B06' else [0,1,2,10,97]) if args.verify_only else case['sizes']
            for n in sizes:
                for language in ('zzy','python'):
                    path = inputs/f'{case["id"]}-{n}.{ "zzy" if language=="zzy" else "py"}'
                    path.write_bytes(source(case,language,n))
                    paths[case['id'],n,language]=path.resolve()
                    for scope in ('cli_total','stages'):
                        jobs.append((case['id'],n,language,scope))
        rng=random.Random(manifest['order_seed'])
        rng.shuffle(jobs)
        active=[]
        batches={}
        for ident,n,language,scope in jobs:
            row=collect(language,scope,ident,n,paths[ident,n,language])
            save(row,'equivalence',0)
            print(f'equivalence {ident}/{n} {language}/{scope}: {row["status"]}',flush=True)
            if row['status']=='ok':
                active.append((ident,n,language,scope))
                if scope=='stages':
                    times=row['timings']
                    batches[ident,n,language]=max(1,min(1000,
                        math.ceil(100_000_000/max(1,times['execute_ns'])),
                        int(5_000_000_000/max(1,sum(times.values())))))
        if not args.verify_only:
            # A language pair/scope must pass both oracles before timing either.
            eligible=[job for job in active if (job[0],job[1],'python' if job[2]=='zzy' else 'zzy',job[3]) in active]
            for job in jobs:
                if job not in eligible:
                    ident,n,language,scope=job
                    save(dict(case=ident,n=n,language=language,scope=scope,status='not_measured',
                              reason='paired equivalence gate failed; no fabricated samples',result_check=False),'gate',0)
            for phase,count in [('warmup',3),('sample',15)]:
                for index in range(count):
                    rng.shuffle(eligible)
                    for ident,n,language,scope in eligible:
                        batch=batches[ident,n,language] if scope=='stages' else 1
                        row=collect(language,scope,ident,n,paths[ident,n,language],batch)
                        save(row,phase,index)
                        if row['status']!='ok':
                            print(f'{phase} {index} {ident}/{n} {language}/{scope}: {row["status"]}',flush=True)
                    print(f'{phase} {index+1}/{count}: {len(eligible)} jobs',flush=True)
    report=summarize(rows)
    (args.output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'records={len(rows)} failure/gate records={len(report["failures"])}',flush=True)
    return 1 if report['failures'] else 0


if __name__=='__main__':
    raise SystemExit(main())
