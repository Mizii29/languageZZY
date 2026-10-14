"""One bounded sample, using real preparation and fresh interpreter state."""
import argparse
import gc
import io
import json
from pathlib import Path
from time import perf_counter_ns

from benchmarks.common import POLICY, digest, validate
from zzy.diagnostics import DiagnosticError, Phase, ResourceExceeded
from zzy.interpreter import Interpreter
from zzy.lexer import Lexer
from zzy.output import Output
from zzy.parser import Parser
from zzy.prepare import prepare
from zzy.resolver import Resolver
from zzy.resources import ResourceMeter
from zzy.source import Source


def plain(value):
    if value.kind == 'Array':
        return [plain(x) for x in value.data]
    if value.kind == 'Quantity':
        number, dimensions = value.data
        return [number.numerator, number.denominator, list(dimensions)]
    if value.kind in {'Int','String','Bool','Null'}:
        return value.data
    raise AssertionError('unexpected benchmark result type')


class SampleInterpreter(Interpreter):
    """Only instrument the top-level boundary; all measured work is real AST."""
    def execute_program(self):
        statements = self.program.root.children
        # Paired sources end in io.print(bench()), plus B05's input dump.
        at = -2 if self.case_id == 'B05' else -1
        output_call = statements[at].children[0]
        call = output_call.children[1]
        if output_call.kind != 'call' or call.kind != 'call' or call.children[0].token.lexeme != 'bench':
            raise AssertionError('benchmark entry must be io.print(bench())')
        for statement in statements[:at]:
            yield from self.statement(statement)
        started = perf_counter_ns()
        self.times['initialize_ns'] = started-self.started
        result = yield from self.evaluate(call)
        stopped = perf_counter_ns()
        self.times['execute_ns'] = stopped-started
        original = None
        if self.case_id == 'B05':
            reference = self.program.references[id(statements[-1].children[0].children[1])]
            values = self.read_reference(reference, call)
            original = plain(values)
            # Equal keys must preserve reference order, not just equal values.
            indices = {id(value):index for index,value in enumerate(values.data)}
            positions = [(value.data, indices[id(value)]) for value in result.data]
            if positions != sorted(positions):
                raise AssertionError('unstable sort or replaced input elements')
        self.result_hash = validate(self.case_id,self.n,plain(result),original)
        self.times['validate_ns'] = perf_counter_ns()-stopped
        self.cleanup_started = perf_counter_ns()
        # Do not retain result Values across run() cleanup or next iteration.


def sample(path, language, case_id, n, batch=1):
    if type(batch) is not int or not 1 <= batch <= 1000:
        raise ValueError('batch must be 1..1000')
    gc.enable()
    started = perf_counter_ns()
    raw = Path(path).read_bytes()
    read_ns = perf_counter_ns()-started
    meter = ResourceMeter(POLICY,Phase.FRONTEND)
    started = perf_counter_ns()
    if language == 'zzy':
        meter.check('source_file_bytes',len(raw))
        meter.check('source_total_bytes',len(raw))
        source = Source.from_bytes(Path(path),raw)
        program = prepare(source,meter)
    else:
        program = compile(raw,str(path),'exec')
    prepare_ns = perf_counter_ns()-started
    timings = dict(read_ns=read_ns,prepare_ns=prepare_ns,initialize_ns=0,
                   execute_ns=0,validate_ns=0,cleanup_ns=0)
    for _ in range(batch):
        started = perf_counter_ns()
        if language == 'zzy':
            output = Output(io.StringIO(),io.StringIO(),ResourceMeter(POLICY,Phase.EXECUTION))
            runtime = SampleInterpreter(program,output,io.StringIO())
            runtime.case_id, runtime.n, runtime.started = case_id,n,started
            runtime.times = {}
            runtime.run()
            runtime.times['cleanup_ns'] = perf_counter_ns()-runtime.cleanup_started
            if any(runtime.meter.used(key) for key in ('runtime_objects','runtime_slots','runtime_payload_bytes')):
                raise AssertionError('context leaked logical reservations')
            result_hash = runtime.result_hash
            for key,value in runtime.times.items():
                timings[key] += value
            del runtime, output
        else:
            namespace = {'__name__':'benchmark_sample'}
            exec(program, namespace)
            ready = perf_counter_ns()
            timings['initialize_ns'] += ready-started
            result = namespace['bench']()
            stopped = perf_counter_ns()
            timings['execute_ns'] += stopped-ready
            normal = ([result[0].numerator,result[0].denominator,list(result[1])]
                      if case_id=='B09' else result)
            result_hash = validate(case_id,n,normal,namespace.get('numbers'))
            validated = perf_counter_ns()
            timings['validate_ns'] += validated-stopped
            if 'checked' in namespace:
                namespace['checked'].close()
            # Break function/global cycles deterministically on both sides.
            namespace.clear()
            del namespace, result, normal
            timings['cleanup_ns'] += perf_counter_ns()-validated
    record = dict(status='ok',result_check=True,result_hash=result_hash,batch=batch,
                  timings=timings,source_sha256=digest(raw),source_bytes=len(raw),
                  gc_enabled=gc.isenabled())
    if language == 'zzy':
        # A separate frontend decomposition probe, not subtracted from prepare.
        probe_meter = ResourceMeter(POLICY,Phase.FRONTEND)
        started = perf_counter_ns()
        tokens = Lexer(source,probe_meter).scan()
        lex_end = perf_counter_ns()
        root = Parser(tokens,probe_meter).parse()
        parse_end = perf_counter_ns()
        Resolver(root,probe_meter).resolve()
        bind_end = perf_counter_ns()
        record['frontend_probe'] = dict(lex_ns=lex_end-started,parse_ns=parse_end-lex_end,
            bind_ns=bind_end-parse_end,tokens=len(tokens),codepoints=len(source.text))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('language',choices=['zzy','python'])
    parser.add_argument('case')
    parser.add_argument('n',type=int)
    parser.add_argument('path',type=Path)
    parser.add_argument('--batch',type=int,default=1)
    args = parser.parse_args()
    try:
        result = sample(args.path,args.language,args.case,args.n,args.batch)
    except (DiagnosticError,ResourceExceeded) as error:
        result = dict(status='resource_failure' if isinstance(error,ResourceExceeded) else 'diagnostic_failure',
                      diagnostic=error.diagnostic.record(),error_phase=error.phase.name,result_check=False)
    except Exception as error:
        result = dict(status='error',error=f'{type(error).__name__}: {error}',result_check=False)
    print(json.dumps(result,separators=(',',':')))
    return 0 if result['status']=='ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
