"""Time matched prepared function calls without CLI startup or result printing."""
import argparse
import gc
from hashlib import sha256
import io
import json
from pathlib import Path
from time import perf_counter_ns

from benchmarks.common import POLICY
from benchmarks.p12.run import expected
from benchmarks.worker import plain
from zzy.diagnostics import Phase, ResourceExceeded
from zzy.interpreter import Interpreter
from zzy.output import Output
from zzy.prepare import prepare
from zzy.resources import ResourceMeter
from zzy.source import Source


class TimedInterpreter(Interpreter):
    def execute_program(self):
        statements = self.program.root.children
        output_call = statements[-1].children[0]
        call = output_call.children[1]
        if (output_call.kind != 'call' or call.kind != 'call'
                or call.children[0].token.lexeme != 'bench'):
            raise AssertionError('last statement must call io.print(bench())')
        for statement in statements[:-1]:
            yield from self.statement(statement)
        ready = perf_counter_ns()
        self.timings['initialize_ns'] = ready - self.started
        result = yield from self.evaluate(call)
        stopped = perf_counter_ns()
        self.timings['execute_ns'] = stopped - ready
        self.value = plain(result)
        if self.value != self.oracle:
            raise AssertionError('ZZY result differs from oracle')
        self.timings['validate_ns'] = perf_counter_ns() - stopped


class LoopReserveInterpreter(TimedInterpreter):
    """Experimental reservation precheck only; not a product runtime change."""
    def reserve(self, node, **amounts):
        limits = self.meter.policy.limits
        for key, count in amounts.items():
            if self.meter.used(key) + count > limits[key]:
                gc.collect()
                break
        try:
            reservation = self.meter.reserve(**amounts)
        except ResourceExceeded as error:
            self.locate_resource_error(error, node)
            raise
        try:
            self.reservations.add(reservation)
        except BaseException:
            reservation.release()
            raise
        return reservation


def measure(path, language, case, n, batch, variant='baseline'):
    if not 1 <= batch <= 100000:
        raise ValueError('batch out of range')
    gc.enable()
    start = perf_counter_ns()
    raw = Path(path).read_bytes()
    read_ns = perf_counter_ns() - start
    start = perf_counter_ns()
    if language == 'zzy':
        meter = ResourceMeter(POLICY, Phase.FRONTEND)
        meter.check('source_file_bytes', len(raw))
        meter.check('source_total_bytes', len(raw))
        program = prepare(Source.from_bytes(Path(path), raw), meter)
    else:
        program = compile(raw, str(path), 'exec')
    prepare_ns = perf_counter_ns() - start
    timings = dict(read_ns=read_ns, prepare_ns=prepare_ns, initialize_ns=0,
                   execute_ns=0, validate_ns=0, cleanup_ns=0)
    oracle = json.loads(expected(case, n))
    for _ in range(batch):
        start = perf_counter_ns()
        if language == 'zzy':
            output = Output(io.StringIO(), io.StringIO(), ResourceMeter(POLICY, Phase.EXECUTION))
            cls = TimedInterpreter if variant == 'baseline' else LoopReserveInterpreter
            runtime = cls(program, output, io.StringIO())
            runtime.started = start
            runtime.timings = {}
            runtime.oracle = oracle
            runtime.run()
            stopped = perf_counter_ns()
            if any(runtime.meter.used(key) for key in
                   ('runtime_objects', 'runtime_slots', 'runtime_payload_bytes')):
                raise AssertionError('ZZY resource reservations leaked')
            for key, elapsed in runtime.timings.items():
                timings[key] += elapsed
            timings['cleanup_ns'] += stopped - start - sum(runtime.timings.values())
            del runtime, output
        else:
            namespace = {'__name__': 'benchmark_sample'}
            exec(program, namespace)
            ready = perf_counter_ns()
            result = namespace['bench']()
            stopped = perf_counter_ns()
            normalized = result
            if normalized != oracle:
                raise AssertionError(f'{case}/{n}: Python result differs from oracle')
            validated = perf_counter_ns()
            namespace.clear()
            del namespace, result, normalized
            cleaned = perf_counter_ns()
            timings['initialize_ns'] += ready - start
            timings['execute_ns'] += stopped - ready
            timings['validate_ns'] += validated - stopped
            timings['cleanup_ns'] += cleaned - validated
    return dict(status='ok', batch=batch, variant=variant, timings=timings,
                value_sha256=sha256(expected(case, n).encode()).hexdigest(),
                gc_enabled=gc.isenabled(), source_sha256=sha256(raw).hexdigest())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('language', choices=('zzy', 'python'))
    parser.add_argument('case', choices=('X00', 'X01', 'X02', 'X03'))
    parser.add_argument('n')
    parser.add_argument('path', type=Path)
    parser.add_argument('--batch', type=int, default=1)
    parser.add_argument('--variant', choices=('baseline', 'reserve-loop'), default='baseline')
    args = parser.parse_args(argv)
    n = None if args.n == 'none' else int(args.n)
    try:
        record = measure(args.path, args.language, args.case, n, args.batch, args.variant)
    except Exception as error:
        record = dict(status='error', error=f'{type(error).__name__}: {error}')
    print(json.dumps(record, ensure_ascii=False, separators=(',', ':')))
    return 0 if record['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
