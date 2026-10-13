"""Private subprocess entry point for one spec, using a collected byte snapshot."""
import json
from pathlib import Path
import sys

from .diagnostics import Diagnostic, DiagnosticError, ResourceExceeded, Cancelled, Phase
from .interpreter import Interpreter
from .output import Output
from .prepare import prepare
from .resources import ResourcePolicy, ResourceMeter
from .source import Source, SourceLoader


def main():
    snapshot, original, index, config = sys.argv[1:]
    for stream in (sys.stdout, sys.stderr, sys.stdin):
        stream.reconfigure(encoding="utf-8", newline="\n")
    policy = ResourcePolicy.from_file(config)
    output = Output(sys.stdout, sys.stderr, ResourceMeter(policy, Phase.FRONTEND), "json")
    try:
        with SourceLoader(output.meter) as loader:
            loaded = loader.read(snapshot)
            source = Source.from_bytes(Path(original), loaded.raw)
            program = prepare(source, output.meter)
        spec = [node for node in program.root.children if node.kind == "spec"][int(index)]
        runtime = Interpreter(program, output)
        runtime.selected_spec = spec
        runtime.run()
        return 0
    except DiagnosticError as error:
        output.failure(error.diagnostic)
        return error.exit_code
    except ResourceExceeded as error:
        output.final(error.diagnostic)
        return error.exit_code
    except (Cancelled, KeyboardInterrupt):
        output.final(Diagnostic("操作已取消", kind="cancelled"))
        return 130
    except (MemoryError, RecursionError) as error:
        output.final(Diagnostic(f"宿主资源不足：{type(error).__name__}", "E211"))
        return 1
    except Exception as error:
        output.final(Diagnostic(f"解释器内部问题：{type(error).__name__}", kind="internal_error"))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
