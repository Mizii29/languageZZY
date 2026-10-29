"""Fresh-process P11 worker; runtime import is selected by the parent snapshot path."""
import argparse
import cProfile
import io
import json
import pstats
from pathlib import Path
from time import perf_counter_ns


def measure(case, n, path, expected):
    import benchmarks.worker as worker
    if case.startswith('B'):
        return worker.sample(path, 'zzy', case, n)
    if case in {'D01', 'D02', 'R01'}:
        from zzy.source import Source
        from zzy.prepare import prepare
        from zzy.resources import ResourceMeter, ResourcePolicy
        from zzy.diagnostics import Phase, ResourceExceeded
        from zzy.interpreter import Interpreter
        from zzy.output import Output
        policy=ResourcePolicy();started=perf_counter_ns()
        program=prepare(Source.from_bytes(Path(path),Path(path).read_bytes()),ResourceMeter(policy,Phase.FRONTEND))
        prepared=perf_counter_ns()
        meter=ResourceMeter(policy,Phase.EXECUTION)
        runtime=Interpreter(program,Output(io.StringIO(),io.StringIO(),meter),io.StringIO())
        node=program.root;ready=perf_counter_ns();failures=0
        for _ in range(n):
            if case=='R01':
                with runtime.reserve(node,runtime_slots=1,runtime_payload_bytes=8):pass
            elif case=='D01':runtime.check('integer_bits',1,node)
            else:
                try:runtime.check('integer_bits',65537,node)
                except ResourceExceeded as error:
                    assert (error.key,error.limit,error.requested,error.phase)==('integer_bits',65536,65537,Phase.EXECUTION)
                    assert error.diagnostic.span==node.token.span
                    failures+=1
        stopped=perf_counter_ns()
        assert failures==(n if case=='D02' else 0)
        assert all(meter.used(k)==0 for k in ('runtime_slots','runtime_objects','runtime_payload_bytes'))
        return dict(status='ok',result_check=True,timings=dict(read_ns=0,prepare_ns=prepared-started,initialize_ns=ready-prepared,execute_ns=stopped-ready,cleanup_ns=perf_counter_ns()-stopped))
    def validate(ident, size, result, original=None):
        if result!=expected:raise AssertionError((ident,result,expected))
        from benchmarks.common import digest
        return digest(json.dumps(result).encode())
    worker.validate=validate
    return worker.sample(path,'zzy',case,n)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('case');parser.add_argument('n',type=int)
    parser.add_argument('path');parser.add_argument('expected');parser.add_argument('--profile')
    args=parser.parse_args()
    try:
        if args.profile:
            profiler=cProfile.Profile();profiler.enable()
        result=measure(args.case,args.n,args.path,json.loads(args.expected))
        if args.profile:
            profiler.disable();stream=io.StringIO()
            pstats.Stats(profiler,stream=stream).sort_stats('cumulative').print_stats(45)
            Path(args.profile).write_text(stream.getvalue(),encoding='utf-8')
        print(json.dumps(result));return 0
    except BaseException as error:
        print(json.dumps(dict(status='error',type=type(error).__name__,message=str(error),result_check=False)))
        return 1


if __name__=='__main__':raise SystemExit(main())
