"""P01 tree-walk execution; no eval/exec or arbitrary Python attributes."""

from dataclasses import dataclass
from weakref import WeakSet

from .diagnostics import Diagnostic, DiagnosticError, Phase, display_path
from .native.metadata import Extension, MetadataRegistry, NativeFunction


PRINT = NativeFunction("io.print", ("value",), "Null", ("stdout",), ("E202", "E211"))
REGISTRY = MetadataRegistry()
REGISTRY.register(Extension("io", "p01-v1", functions=(PRINT,)))


class Value:
    """One owned scalar payload, shared by aliases; P01 values contain no cycles."""

    def __init__(self, kind, data, reservation=None):
        self.kind, self.data, self.reservation = kind, data, reservation

    def __del__(self):
        if getattr(self, "reservation", None) is not None:
            self.reservation.release()


NULL = Value("Null", None)


@dataclass
class Binding:
    value: Value
    mutable: bool
    annotation: str | None = None


class Interpreter:
    def __init__(self, program, output):
        self.program, self.output = program, output
        self.meter = output.meter
        self.file = display_path(program.root.token.source.path)
        self.bindings = {}
        self.slots = []
        self.reservations = WeakSet()

    def error(self, node, code, message):
        raise DiagnosticError(Diagnostic(message, code, self.file, node.token.span), Phase.EXECUTION)

    def check(self, key, count, node):
        self.meter.check(key, count, file=self.file, span=node.token.span)

    def reserve(self, node, **amounts):
        reservation = self.meter.reserve(file=self.file, span=node.token.span, **amounts)
        self.reservations.add(reservation)
        return reservation

    def scalar(self, kind, data, node):
        if kind == "Int":
            self.check("integer_bits", data.bit_length(), node)
            size = (data.bit_length() + 7) // 8
        else:
            self.check("text_codepoints", len(data), node)
            size = 4 * len(data)
        return Value(kind, data, self.reserve(node, runtime_payload_bytes=size))

    def run(self):
        self.meter.phase = Phase.EXECUTION
        try:
            # The frame's io slot and the namespace's print slot own two references.
            self.slots.append(self.reserve(self.program.root, runtime_objects=2, runtime_slots=2))
            function = Value("Function", PRINT)
            self.bindings["io"] = Binding(Value("Namespace", {"print": function}), False)
            for statement in self.program.root.children:
                self.meter.cancellation.check()
                self.statement(statement)
        finally:
            self.bindings.clear()
            for reservation in self.slots:
                reservation.release()
            self.slots.clear()
            # Exception tracebacks may retain evaluation frames and their values.
            # The terminated context releases even those no-longer-usable owners.
            for reservation in list(self.reservations):
                reservation.release()
            self.reservations.clear()

    def typecheck(self, annotation, value, node):
        if annotation is not None and value.kind != annotation:
            raise DiagnosticError(Diagnostic(f"注解要求 {annotation}，实际为 {value.kind}",
                                             "E201", self.file, node.span), Phase.EXECUTION)

    def statement(self, node):
        if node.kind == "binding":
            mutable, annotation = node.data
            kind = annotation.lexeme[1:-1] if annotation is not None else None
            slot = self.reserve(node, runtime_slots=1)
            try:
                value = self.evaluate(node.children[0])
                self.typecheck(kind, value, node.children[0])
                self.bindings[node.token.lexeme] = Binding(value, mutable, kind)
                self.slots.append(slot)
            except BaseException:
                slot.release()
                raise
        elif node.kind == "assignment":
            target, expression = node.children
            if target.kind == "field":
                owner = self.evaluate(target.children[0])
                if owner.kind != "Namespace":
                    self.error(target, "E201", "此值不支持字段写入")
                self.error(target, "E203", "命名空间字段只读")
            binding = self.bindings[target.data]
            if not binding.mutable:
                self.error(target, "E203", f"名称 {target.data} 不允许重新绑定")
            value = self.evaluate(expression)
            self.typecheck(binding.annotation, value, expression)
            binding.value = value
        else:
            self.evaluate(node.children[0])

    def evaluate(self, node):
        self.meter.cancellation.check()
        if node.kind == "integer":
            return self.scalar("Int", self.program.integers[id(node)], node)
        if node.kind == "string":
            return self.scalar("String", node.data, node)
        if node.kind == "name":
            return self.bindings[node.data].value
        if node.kind == "group":
            return self.evaluate(node.children[0])
        if node.kind == "field":
            owner = self.evaluate(node.children[0])
            if owner.kind != "Namespace":
                self.error(node, "E201", "此值不支持字段访问")
            if node.data not in owner.data:
                self.error(node, "E302", f"字段 {node.data} 尚未实现或不存在")
            return owner.data[node.data]
        if node.kind == "add":
            left = self.evaluate(node.children[0])
            right = self.evaluate(node.children[1])
            if left.kind != right.kind or left.kind not in {"Int", "String"}:
                self.error(node, "E201", "+ 需要两个 Int 或两个 String；不隐式转换")
            if left.kind == "String":
                size = len(left.data) + len(right.data)
                self.check("text_codepoints", size, node)
                reservation = self.reserve(node, runtime_payload_bytes=4 * size)
            else:
                scratch = (max(left.data.bit_length(), right.data.bit_length()) + 7) // 8
                with self.reserve(node, runtime_payload_bytes=scratch):
                    bits = self.add_bits(left.data, right.data)
                self.check("integer_bits", bits, node)
                reservation = self.reserve(node, runtime_payload_bytes=(bits + 7) // 8)
            try:
                return Value(left.kind, left.data + right.data, reservation)
            except BaseException:
                reservation.release()
                raise
        if node.kind == "call":
            function = self.evaluate(node.children[0])
            with self.reserve(node, runtime_slots=len(node.children) - 1):
                arguments = [self.evaluate(arg) for arg in node.children[1:]]
                if function.kind != "Function":
                    self.error(node, "E202", "此值不可调用")
                if len(arguments) != len(function.data.parameters):
                    self.error(node, "E202", "io.print 恰好需要一个参数")
                return self.print_value(arguments[0], node)
        raise AssertionError(f"unknown expression node: {node.kind}")

    def add_bits(self, left, right):
        """Exact nonnegative sum width without allocating the result first.

        Scan bounded byte chunks for the final carry, with reserved shift scratch.
        This avoids rejecting a result merely because an upper bound is too large.
        Signed arithmetic belongs to P02.
        """
        width = max(left.bit_length(), right.bit_length())
        if not width:
            return 0
        carry = 0
        high = 0
        for shift in range(0, width, 8):
            self.meter.cancellation.check()
            chunk = ((left >> shift) & 255) + ((right >> shift) & 255) + carry
            carry = chunk >> 8
            high = chunk & 255
        return shift + 8 + 1 if carry else shift + high.bit_length()

    def print_value(self, value, node):
        if value.kind == "Int":
            with self.reserve(node, runtime_payload_bytes=(value.data.bit_length() + 7) // 8):
                remaining, digits = value.data, 0
                while remaining >= 1_000_000_000:
                    self.meter.cancellation.check()
                    remaining //= 1_000_000_000
                    digits += 9
                digits += len(str(remaining))
            self.check("numeric_digits", digits, node)
            self.check("text_codepoints", digits, node)
            # str(Int) and its LF-appended copy coexist during concatenation.
            with self.reserve(node, runtime_payload_bytes=4 * (2 * digits + 1)):
                self.output.write(str(value.data) + "\n")
            return NULL
        elif value.kind == "String":
            text = value.data
        elif value.kind == "Null":
            text = "null"
        elif value.kind == "Function":
            text = f"<function {value.data.name}>"
        else:
            text = "<module io>"
        self.check("text_codepoints", len(text), node)
        # Formatting and the appended LF are bounded temporary text payloads.
        with self.reserve(node, runtime_payload_bytes=4 * (len(text) + 1)):
            self.output.write(text + "\n")
        return NULL
