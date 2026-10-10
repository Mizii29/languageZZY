"""Infrastructure, lexical inspection and execution of the P01 subset."""

import argparse
import json
import platform
import sys
import unicodedata

from . import __version__
from .diagnostics import (Cancelled, Diagnostic, DiagnosticError, Phase,
                          ResourceExceeded, display_path)
from .output import Output
from .lexer import Lexer
from .prepare import prepare
from .interpreter import Interpreter
from .resources import ResourceMeter, ResourcePolicy
from .source import SourceLoader


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise DiagnosticError(Diagnostic(message, "E401"))

    def _print_message(self, message, file=None):
        if message:
            self.output.write(message)


def _parser(output: Output) -> ArgumentParser:
    common = argparse.ArgumentParser(add_help=False, argument_default=argparse.SUPPRESS)
    common.add_argument("--limits", metavar="JSON", help="资源策略覆盖文件（最多 64 KiB）")
    common.add_argument("--diagnostic-format", choices=("text", "json"), help="stderr 诊断格式")
    parser = ArgumentParser(prog="zzy", parents=[common],
                            description="ZZY P01：词法扫描及最小 AST 执行；check/test 尚未实现。",
                            allow_abbrev=False)
    parser.output = output
    parser.add_argument("--version", action="version", version=f"ZZY {__version__} (P01 interpreter)")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help in (("info", "输出宿主环境、生效策略及指纹"),
                       ("source-info", "读取 UTF-8 源码并输出摘要，不做语法检查"),
                       ("lex", "扫描词法并输出 Token JSON Lines；不解析、不执行"),
                       ("run", "执行 P01 子集：声明、赋值、Int/String 加法和 io.print")):
        subparser = commands.add_parser(name, parents=[common], help=help, allow_abbrev=False)
        subparser.output = output
        if name in {"source-info", "lex", "run"}:
            subparser.add_argument("file", help="相对当前工作目录的源码路径")
    return parser


def _requested_format(argv: list[str]) -> str:
    # Select JSON even when full argument parsing fails; stop at the literal separator.
    format = "text"
    for index, arg in enumerate(argv):
        if arg == "--":
            break
        if arg.startswith("--diagnostic-format="):
            value = arg.partition("=")[2]
        elif arg == "--diagnostic-format" and index + 1 < len(argv):
            value = argv[index + 1]
        else:
            continue
        if value in {"json", "text"}:
            format = value
    return format


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="strict" if stream is sys.stdin
                               else "backslashreplace", newline="\n")
    output = Output(sys.stdout, sys.stderr, ResourceMeter(ResourcePolicy(), Phase.FRONTEND),
                    _requested_format(argv))
    try:
        args = _parser(output).parse_args(argv)
        policy = ResourcePolicy.from_file(args.limits) if hasattr(args, "limits") else ResourcePolicy()
        output.meter = ResourceMeter(policy, Phase.FRONTEND)
        output.format = getattr(args, "diagnostic_format", output.format)
        if args.command == "info":
            result = {
                "zzy_version": __version__, "stage": "P01-02",
                "python_implementation": platform.python_implementation(),
                "python_version": sys.version, "python_executable": sys.executable,
                "unicode_version": unicodedata.unidata_version,
                "platform": platform.platform(),
                "resource_policy": policy.effective_record(),
                "resource_fingerprint": policy.fingerprint,
            }
        else:
            with SourceLoader(output.meter) as loader:
                source = loader.read(args.file)
                if args.command == "run":
                    program = prepare(source, output.meter)
                    Interpreter(program, output).run()
                    return 0
                if args.command == "lex":
                    # Finish scanning first: lexical failure emits no token prefix.
                    # Each output record is budgeted; later output exhaustion may
                    # leave complete earlier records, but always exits nonzero.
                    for token in Lexer(source, output.meter).scan():
                        output.write(json.dumps(token.record(), ensure_ascii=False,
                                                separators=(",", ":")) + "\n")
                    return 0
                result = {"file": display_path(source.path), "bytes": len(source.raw),
                          "codepoints": len(source.text), "lines": len(source.line_starts),
                          "sha256": source.sha256, "syntax_checked": False,
                          "resource_fingerprint": policy.fingerprint}
        output.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
        return 0
    except DiagnosticError as error:
        output.failure(error.diagnostic)
        return error.exit_code
    except ResourceExceeded as error:
        output.final(error.diagnostic)
        return error.exit_code
    except (KeyboardInterrupt, Cancelled):
        output.final(Diagnostic("操作已取消", kind="cancelled"))
        return 130
    except (MemoryError, RecursionError) as error:
        output.final(Diagnostic(f"宿主资源不足：{type(error).__name__}", "E211"))
        return output.meter.phase.value
    except Exception as error:
        output.final(Diagnostic(f"解释器内部问题：{type(error).__name__}", kind="internal_error"))
        return output.meter.phase.value
