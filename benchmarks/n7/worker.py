"""Run one staged sample. The parent checks the fixed stdout oracle."""
import contextlib
import io
import json
from pathlib import Path
import sys
from time import perf_counter_ns as now


def sample(backend, path, limits, logical=False):
    # Imports and policy parsing are outside the staged window for both hosts.
    if backend == 'hosted':
        from zzy.diagnostics import Phase
        from zzy.interpreter import Interpreter
        from zzy.output import Output
        from zzy.prepare import prepare
        from zzy.resources import ResourceMeter, ResourcePolicy
        from zzy.source import Source

        class TimedInterpreter(Interpreter):
            def execute_program(self):
                self.initialized = now()
                yield from super().execute_program()
                self.executed = now()

        class TracingMeter(ResourceMeter):
            def reserve(self, **kwargs):
                reservation = super().reserve(**kwargs)
                for key in keys:
                    peak[key] = max(peak[key], self.used(key))
                return reservation

        policy = ResourcePolicy.from_file(limits)
        meter = ResourceMeter(policy, Phase.FRONTEND)
        keys = ('runtime_objects', 'runtime_slots', 'runtime_payload_bytes')
        peak = dict.fromkeys(keys, 0)

    out, err = io.StringIO(), io.StringIO()
    start = now()
    raw = path.read_bytes()
    read = now()
    if backend == 'hosted':
        meter.check('source_file_bytes', len(raw))
        meter.check('source_total_bytes', len(raw))
        meter.check('import_depth', 1)
        meter.check('module_count', 1)
        program = prepare(Source.from_bytes(path, raw), meter)
        prepared = now()
        runtime_meter = (TracingMeter if logical else ResourceMeter)(policy, Phase.EXECUTION)
        runtime = TimedInterpreter(program, Output(out, err, runtime_meter), io.StringIO())
        runtime.run()
        initialized, executed = runtime.initialized, runtime.executed
        if any(runtime_meter.used(key) for key in keys):
            raise RuntimeError('request quota not released')
        del runtime, runtime_meter
    else:
        program = compile(raw, str(path), 'exec')
        prepared = now()
        namespace = {'__name__': '__main__', '__file__': str(path)}
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            initialized = now()
            exec(program, namespace)
            executed = now()
            namespace.clear()
    del program, raw
    cleaned = now()
    result = dict(read_ns=read-start, prepare_ns=prepared-read,
                  init_ns=initialized-prepared, execute_ns=executed-initialized,
                  cleanup_ns=cleaned-executed, stdout=out.getvalue(), stderr=err.getvalue())
    if backend == 'hosted' and logical:
        result['logical_peak'] = peak
    return result


if __name__ == '__main__':
    backend, path, limits, *flags = sys.argv[1:]
    print(json.dumps(sample(backend, Path(path), Path(limits), '--logical' in flags)))
