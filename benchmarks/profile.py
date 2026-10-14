"""Separate diagnostic probes; never use these timings as speed samples."""
import argparse
import cProfile
import io
import json
from pathlib import Path
import pstats
import tracemalloc

from benchmarks.common import BASE, ROOT, POLICY, digest, load_manifest
from benchmarks.run import git
from benchmarks.worker import sample


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',required=True)
    parser.add_argument('--n',type=int,required=True)
    parser.add_argument('--memory',action='store_true')
    args=parser.parse_args()
    if args.case not in {case['id'] for case in load_manifest()['cases']}:
        raise ValueError('unknown case')
    path=(args.inputs/f'{args.case}-{args.n}.zzy').resolve()
    args.output.mkdir(parents=True,exist_ok=False)
    metadata=dict(case=args.case,n=args.n,revision=git('rev-parse','HEAD'),git_status=git('status','--short'),
        source_sha256=digest(path.read_bytes()),source=str(path),resource_fingerprint=POLICY.fingerprint,
        tool='tracemalloc' if args.memory else 'cProfile',timings_not_performance_samples=True,
        scope='sample: read, prepare, fresh initialization, real task, validate, cleanup and frontend probe')
    if args.memory:
        tracemalloc.start()
        result=sample(path,'zzy',args.case,args.n)
        current,peak=tracemalloc.get_traced_memory()
        tracemalloc.stop()
        metadata.update(current_python_bytes=current,peak_python_bytes=peak,
                        limitation='Python traced allocations only; not native allocations or process RSS')
    else:
        profiler=cProfile.Profile()
        result=profiler.runcall(sample,path,'zzy',args.case,args.n)
        profiler.dump_stats(str(args.output/'profile.pstats'))
        stream=io.StringIO()
        stats=pstats.Stats(profiler,stream=stream)
        stats.sort_stats('cumulative').print_stats(50)
        stats.sort_stats('tottime').print_stats(30)
        (args.output/'profile.txt').write_text(stream.getvalue(),encoding='utf-8')
        metadata['total_profiled_seconds']=stats.total_tt
        metadata['functions']=[dict(file=key[0],line=key[1],function=key[2],primitive_calls=value[0],
            calls=value[1],self_seconds=value[2],cumulative_seconds=value[3])
            for key,value in sorted(stats.stats.items(),key=lambda pair:pair[1][3],reverse=True)[:80]]
    metadata.update(result_check=result['result_check'],result_hash=result['result_hash'])
    (args.output/'probe.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in metadata.items() if k!='functions'},ensure_ascii=False))


if __name__=='__main__':main()
