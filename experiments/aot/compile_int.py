"""Experimental AOT compiler for pure, scalar Int ZZY functions.

This is an opt-in research tool, not the course interpreter or a full ZZY
implementation. It uses the real lexer, parser and resolver and refuses every
construct that has not been translated deliberately.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess

from zzy.ast_nodes import Node, Program
from zzy.diagnostics import Phase
from zzy.prepare import prepare
from zzy.resources import ResourceMeter, ResourcePolicy
from zzy.source import SourceLoader


MAX_INT = (1 << 63) - 1


class Unsupported(ValueError):
    """The experimental subset cannot preserve this ZZY construct."""


def reject(node: Node, reason: str) -> None:
    span = node.span
    raise Unsupported(f"{node.token.source.path}:{span.start.line}:{span.start.column}: {reason}")


def annotation_is_int(token) -> bool:
    return token is not None and token.lexeme == "(Int)"


class Generator:
    def __init__(self, program: Program, entry: str):
        self.program = program
        self.entry = entry
        self.functions: dict[int, Node] = {}
        self.names: dict[int, str] = {}
        self.variables: dict[int, str] = {}
        self.serial = 0
        self.calls: dict[int, set[int]] = {}
        self.current_function = 0

    def next_var(self, prefix="t") -> str:
        name = f"{prefix}{self.serial}"
        self.serial += 1
        return name

    def function_target(self, node: Node) -> int:
        if node.kind != "name":
            reject(node, "only direct calls to top-level functions are supported")
        reference = self.program.references[id(node)]
        if reference.symbol not in self.functions:
            reject(node, "callee is not an AOT-supported top-level function")
        return reference.symbol

    def expression(self, node: Node, depth: int) -> tuple[list[str], str, str]:
        pad = "    " * depth
        if node.kind == "group":
            return self.expression(node.children[0], depth)
        if node.kind == "integer":
            number = self.program.integers[id(node)]
            if number < 0 or number > MAX_INT:
                reject(node, "literal does not fit the AOT Int64 subset")
            result = self.next_var()
            return [f"{pad}int64_t {result} = INT64_C({number});"], result, "Int"
        if node.kind == "name":
            reference = self.program.references[id(node)]
            if reference.symbol not in self.variables:
                reject(node, "only local Int bindings are supported as values")
            return [], self.variables[reference.symbol], "Int"
        if node.kind == "unary":
            lines, value, kind = self.expression(node.children[0], depth)
            if kind != "Int" or node.token.lexeme not in {"+", "-"}:
                reject(node, "only unary Int +/- are supported")
            if node.token.lexeme == "+":
                return lines, value, "Int"
            result = self.next_var()
            lines.append(f"{pad}int64_t {result} = zzy_neg({value});")
            return lines, result, "Int"
        if node.kind == "call":
            target = self.function_target(node.children[0])
            callee = self.functions[target]
            if len(node.children) - 1 != len(callee.children) - 1:
                reject(node, "incorrect number of arguments")
            lines, values = [], []
            for argument in node.children[1:]:
                part, value, kind = self.expression(argument, depth)
                if kind != "Int":
                    reject(argument, "function argument must be Int")
                lines.extend(part)
                values.append(value)
            self.calls[self.current_function].add(target)
            result = self.next_var()
            lines.append(f"{pad}int64_t {result} = {self.names[target]}({', '.join(values)});")
            return lines, result, "Int"
        if node.kind in {"add", "binary"}:
            left_lines, left, left_kind = self.expression(node.children[0], depth)
            right_lines, right, right_kind = self.expression(node.children[1], depth)
            if left_kind != "Int" or right_kind != "Int":
                reject(node, "only Int operands are supported")
            lines = left_lines + right_lines
            result = self.next_var()
            operator = node.token.lexeme
            helpers = {"+": "zzy_add", "-": "zzy_sub", "*": "zzy_mul", "%": "zzy_mod"}
            if operator in helpers:
                lines.append(f"{pad}int64_t {result} = {helpers[operator]}({left}, {right});")
                return lines, result, "Int"
            if operator in {"<", "<=", ">", ">=", "==", "!="}:
                lines.append(f"{pad}bool {result} = {left} {operator} {right};")
                return lines, result, "Bool"
            reject(node, f"operator {operator} is not supported")
        reject(node, f"{node.kind} is not supported by the Int64 AOT pilot")

    def statements(self, statements: tuple[Node, ...], depth: int) -> list[str]:
        lines: list[str] = []
        pad = "    " * depth
        for node in statements:
            if node.kind == "binding":
                if node.data[1] is not None and not annotation_is_int(node.data[1]):
                    reject(node, "only Int local annotations are supported")
                prefix, value, kind = self.expression(node.children[0], depth)
                if kind != "Int":
                    reject(node, "local binding must have an Int initializer")
                name = self.next_var("v")
                self.variables[id(node)] = name
                lines.extend(prefix)
                lines.append(f"{pad}int64_t {name} = {value};")
            elif node.kind == "assignment":
                target = node.children[0]
                if target.kind != "name":
                    reject(target, "only local name assignment is supported")
                reference = self.program.references[id(target)]
                symbol = reference.symbol
                if symbol not in self.variables or not self.program.symbols[symbol].mutable:
                    reject(target, "assignment requires a mutable local Int binding")
                prefix, value, kind = self.expression(node.children[1], depth)
                if kind != "Int":
                    reject(node, "assigned value must be Int")
                lines.extend(prefix)
                lines.append(f"{pad}{self.variables[symbol]} = {value};")
            elif node.kind == "while":
                lines.append(f"{pad}while (true) {{")
                prefix, condition, kind = self.expression(node.children[0], depth + 1)
                if kind != "Bool":
                    reject(node.children[0], "while condition must be Bool")
                lines.extend(prefix)
                lines.append(f"{pad}    if (!{condition}) break;")
                lines.extend(self.statements(node.children[1].children, depth + 1))
                lines.append(f"{pad}}}")
            elif node.kind == "if":
                lines.extend(self.if_statement(node.children, depth))
            elif node.kind == "return":
                if len(node.children) != 1:
                    reject(node, "Int function must return an Int")
                prefix, value, kind = self.expression(node.children[0], depth)
                if kind != "Int":
                    reject(node, "return value must be Int")
                lines.extend(prefix)
                lines.append(f"{pad}return {value};")
            else:
                reject(node, f"statement {node.kind} is not supported")
        return lines

    def if_statement(self, parts: tuple[Node, ...], depth: int) -> list[str]:
        pad = "    " * depth
        if len(parts) == 1:
            return self.statements(parts[0].children, depth)
        prefix, condition, kind = self.expression(parts[0], depth)
        if kind != "Bool":
            reject(parts[0], "if condition must be Bool")
        lines = prefix + [f"{pad}if ({condition}) {{"]
        lines.extend(self.statements(parts[1].children, depth + 1))
        lines.append(f"{pad}}}")
        if len(parts) > 2:
            lines[-1] = f"{pad}}} else {{"
            lines.extend(self.if_statement(parts[2:], depth + 1))
            lines.append(f"{pad}}}")
        return lines

    def function(self, symbol: int, node: Node) -> str:
        self.current_function = symbol
        self.variables = {}
        parameters = node.children[:-1]
        for parameter in parameters:
            self.variables[id(parameter)] = self.next_var("v")
        signature = ", ".join(f"int64_t {self.variables[id(p)]}" for p in parameters) or "void"
        body = node.children[-1]
        if body.kind != "block" or not body.children or body.children[-1].kind != "return":
            reject(node, "function must end with an explicit Int return")
        lines = self.statements(body.children, 1)
        return f"static int64_t {self.names[symbol]}({signature}) {{\n" + "\n".join(lines) + "\n}"

    def check_calls_acyclic(self) -> None:
        visiting, visited = set(), set()

        def visit(symbol):
            if symbol in visiting:
                reject(self.functions[symbol], "recursive calls are not supported by this pilot")
            if symbol in visited:
                return
            visiting.add(symbol)
            for target in self.calls[symbol]:
                visit(target)
            visiting.remove(symbol)
            visited.add(symbol)

        for symbol in self.functions:
            visit(symbol)

    def render(self) -> str:
        if self.program.modules:
            reject(self.program.root, "modules are not supported")
        for node in self.program.root.children:
            if node.kind != "function":
                reject(node, "top level may contain only function declarations")
            if not annotation_is_int(node.data):
                reject(node, "every function needs an Int return annotation")
            if any(not annotation_is_int(p.data) for p in node.children[:-1]):
                reject(node, "every parameter needs an Int annotation")
            if any(c.source.symbol not in {id(f) for f in self.program.root.children}
                   for c in self.program.functions[id(node)].captures):
                reject(node, "captured values and closures are not supported")
            symbol = id(node)
            self.functions[symbol] = node
            self.names[symbol] = f"f{len(self.functions) - 1}"
            self.calls[symbol] = set()
        entry_node = next((n for n in self.functions.values() if n.token.lexeme == self.entry), None)
        if entry_node is None or len(entry_node.children) != 2:
            reject(self.program.root, "entry must be a one-argument Int function")
        declarations = []
        for symbol, node in self.functions.items():
            arguments = ", ".join("int64_t" for _ in node.children[:-1]) or "void"
            declarations.append(f"static int64_t {self.names[symbol]}({arguments});")
        definitions = [self.function(symbol, node) for symbol, node in self.functions.items()]
        self.check_calls_acyclic()
        preamble = r'''/* Generated from ZZY's prepared AST. Int64 AOT pilot; not full ZZY. */
#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#ifdef _WIN32
#include <windows.h>
#include <psapi.h>
#endif

static void zzy_fail(const char *message) {
    fprintf(stderr, "AOT subset error: %s\n", message);
    exit(1);
}
static inline int64_t zzy_add(int64_t a, int64_t b) {
    int64_t r;
    if (__builtin_add_overflow(a, b, &r)) zzy_fail("Int64 overflow");
    return r;
}
static inline int64_t zzy_sub(int64_t a, int64_t b) {
    int64_t r;
    if (__builtin_sub_overflow(a, b, &r)) zzy_fail("Int64 overflow");
    return r;
}
static inline int64_t zzy_mul(int64_t a, int64_t b) {
    int64_t r;
    if (__builtin_mul_overflow(a, b, &r)) zzy_fail("Int64 overflow");
    return r;
}
static inline int64_t zzy_neg(int64_t a) {
    return zzy_sub(INT64_C(0), a);
}
static inline int64_t zzy_mod(int64_t a, int64_t b) {
    if (b == 0) zzy_fail("division by zero");
    if (a == INT64_MIN && b == -1) return 0;
    int64_t r = a % b;
    if (r && ((r < 0) != (b < 0))) r = zzy_add(r, b);
    return r;
}
static int64_t parse_int(const char *text) {
    char *end;
    errno = 0;
    intmax_t value = strtoimax(text, &end, 10);
    if (errno || end == text || *end || value < INT64_MIN || value > INT64_MAX)
        zzy_fail("argument must be Int64");
    return (int64_t)value;
}
'''
        main = f'''int main(int argc, char **argv) {{
    if (argc != 2 && argc != 3) zzy_fail("usage: program N [REPEAT]");
    volatile int64_t n = parse_int(argv[1]);
    int64_t repeat = argc == 3 ? parse_int(argv[2]) : 1;
    if (repeat < 1 || repeat > 100000) zzy_fail("REPEAT must be 1..100000");
    int64_t result = 0, checksum = 0;
#ifdef _WIN32
    LARGE_INTEGER frequency, started, ended;
    QueryPerformanceFrequency(&frequency);
    QueryPerformanceCounter(&started);
#endif
    for (int64_t k = 0; k < repeat; ++k) {{
        result = {self.names[id(entry_node)]}(n);
        checksum = zzy_add(checksum, result);
    }}
#ifdef _WIN32
    QueryPerformanceCounter(&ended);
    uint64_t elapsed = (uint64_t)((ended.QuadPart - started.QuadPart) * 1000000000ULL
                                  / (uint64_t)frequency.QuadPart);
    PROCESS_MEMORY_COUNTERS counters;
    counters.cb = sizeof(counters);
    if (!GetProcessMemoryInfo(GetCurrentProcess(), &counters, sizeof(counters)))
        zzy_fail("memory measurement failed");
    fprintf(stderr, "EXECUTE_NS=%" PRIu64 "\\nPEAK_WORKING_SET_BYTES=%" PRIu64 "\\n",
            elapsed, (uint64_t)counters.PeakWorkingSetSize);
#endif
    if (repeat == 1) printf("%" PRId64 "\\n", result);
    else printf("%" PRId64 " %" PRId64 "\\n", result, checksum);
    return 0;
}}'''
        return preamble + "\n" + "\n".join(declarations) + "\n\n" + "\n\n".join(definitions) + "\n\n" + main + "\n"


def render_file(path: Path, entry="bench") -> str:
    meter = ResourceMeter(ResourcePolicy(), Phase.FRONTEND)
    with SourceLoader(meter) as loader:
        program = prepare(loader.read(path), meter, loader)
    return Generator(program, entry).render()


def compile_file(path: Path, output: Path, entry="bench", compiler="gcc") -> tuple[Path, Path]:
    found = shutil.which(compiler)
    if found is None:
        raise RuntimeError(f"C compiler {compiler!r} is unavailable")
    source = render_file(path, entry)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    c_path = output.with_suffix(".c")
    c_path.write_text(source, encoding="utf-8", newline="\n")
    command = [found, "-O3", "-std=c11", "-Wall", "-Wextra", "-Werror",
               str(c_path), "-o", str(output)]
    if os.name == "nt":
        command.append("-lpsapi")
    result = subprocess.run(command, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=60, check=False)
    if result.returncode:
        raise RuntimeError(f"C compiler exited {result.returncode}: {result.stderr}")
    return c_path, output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--entry", default="bench")
    parser.add_argument("--compiler", default="gcc")
    args = parser.parse_args(argv)
    try:
        source, binary = compile_file(args.source, args.output, args.entry, args.compiler)
    except (Unsupported, RuntimeError, OSError) as error:
        parser.exit(1, f"{error}\n")
    print(f"generated {source}\ncompiled {binary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
