"""AST tree walking with slotted frames and an explicit user-call stack."""

from contextlib import contextmanager, nullcontext
from dataclasses import replace
import gc
import math
import operator
import sys
from weakref import WeakSet

from .features import Features
from . import quantities
from .diagnostics import Diagnostic, DiagnosticError, Phase, ResourceExceeded, display_path
from .native.metadata import NativeFunction
from .values import (Array, Binding, CallRequest, Cell, Closure, Frame, LoopSignal,
                     NULL, ReturnSignal, Value, WakeRequest, boolean)


from .native.catalog import FUNCTIONS, REGISTRY, NAMESPACES
from .native.library import Library
PRINT = FUNCTIONS["io.print"]


class Interpreter(Features, Library):
    def __init__(self, program, output, stdin=None):
        self.program, self.output = program, output
        self.stdin = sys.stdin if stdin is None else stdin
        self.meter = output.meter
        self.file = display_path(program.root.token.source.path)
        self.bindings = {}
        self.scopes = [self.bindings]
        self.slots = []
        self.reservations = WeakSet()
        self.frame = None
        self.call_depth = 0
        self.current_item = None
        self.selected_spec = None
        self.modules = {}

    def location(self, node):
        return display_path(node.token.source.path)

    def error(self, node, code, message):
        raise DiagnosticError(Diagnostic(message, code, self.location(node), node.token.span), Phase.EXECUTION)

    def check(self, key, count, node):
        self.meter.check(key, count, file=self.location(node), span=node.token.span)

    def reserve(self, node, **amounts):
        # A dead container cycle must not keep a live-value quota occupied.
        if any(self.meter.used(key) + n > self.meter.policy.limits[key] for key, n in amounts.items()):
            gc.collect()
        reservation = self.meter.reserve(file=self.location(node), span=node.token.span, **amounts)
        self.reservations.add(reservation)
        return reservation

    def scalar(self, kind, data, node):
        if kind == "Int":
            self.check("integer_bits", data.bit_length(), node)
            size = (data.bit_length() + 7) // 8
        elif kind == "Float":
            if not math.isfinite(data):
                self.error(node, "E208", "Float 结果必须有限")
            size = 8
        else:
            self.check("text_codepoints", len(data), node)
            size = 4 * len(data)
        return Value(kind, data, self.reserve(node, runtime_payload_bytes=size))

    def run(self):
        self.meter.phase = Phase.EXECUTION
        try:
            self.slots.append(self.reserve(self.program.root, runtime_objects=2, runtime_slots=2))
            self.bindings["io"] = Binding(Value("Namespace", {"print": Value("Function", PRINT)}), False)
            self.bindings["io"].value.namespace = "io"
            self.drive(self.execute_program())
        finally:
            self.frame = None
            self.call_depth = 0
            self.modules.clear()
            self.bindings.clear()
            self.scopes[:] = [self.bindings]
            for reservation in self.slots:
                reservation.release()
            self.slots.clear()
            for reservation in list(self.reservations):
                reservation.release()
            self.reservations.clear()

    def execute_program(self):
        for statement in self.program.root.children:
            if statement.kind != "spec":
                (yield from self.statement(statement))
        if self.selected_spec is not None:
            yield from self.block(self.selected_spec.children[0])

    def drive(self, generator):
        # Suspended AST walks do not consume the host's recursive call stack.
        # Each user call gets a separate generator and an accounted local frame.
        stack, value, failure = [generator], None, None
        try:
            while stack:
                try:
                    request = stack[-1].throw(failure) if failure is not None else stack[-1].send(value)
                except StopIteration as stopped:
                    stack.pop()
                    value, failure = [stopped.value], None
                except BaseException as error:
                    stack.pop()
                    value, failure = None, error
                else:
                    if not isinstance(request, (CallRequest, WakeRequest)):
                        raise AssertionError("unknown execution request")
                    stack.append(self.execute_lazy(request) if isinstance(request, WakeRequest) else self.execute_user(request))
                    request = None
                    value, failure = None, None
            if failure is not None:
                raise failure
            return value[0] if value else None
        finally:
            for active in reversed(stack):
                active.close()

    def raw_reference(self, reference, node):
        if reference.kind == "global":
            return self.lookup(reference.key, node)
        if reference.kind == "self":
            return self.frame.function
        if reference.kind == "local":
            return self.frame.locals[reference.key]
        return self.frame.function.data.captures[reference.key]

    def read_reference(self, reference, node):
        value = self.raw_reference(reference, node)
        return value.value if isinstance(value, Binding) else value

    def define(self, symbol, value, annotation, node):
        info = self.program.symbols[symbol]
        stored = Cell(value, annotation, self.reserve(node, runtime_slots=1)) if info.cell else value
        if info.owner is not None:
            self.frame.locals[info.slot] = stored
            self.frame.annotations[info.slot] = annotation
        else:
            self.scopes[-1][symbol] = stored if info.cell else Binding(value, info.mutable, annotation)

    def make_function(self, node):
        plan = self.program.functions[id(node)]
        # One slot for each captured reference, plus any nominal type references.
        parameter_types = tuple(self.annotation(p.data, p) for p in node.children[:-1])
        return_type = None if node.kind == "lazy" else self.annotation(node.data, node)
        type_slots = sum(isinstance(t, Value) for t in (*parameter_types, return_type))
        function = Value("Function", None, self.reserve(node, runtime_objects=1,
                           runtime_slots=len(plan.captures) + type_slots))
        captures = []
        for capture in plan.captures:
            raw = self.raw_reference(capture.source, node)
            captures.append(raw if isinstance(raw, Cell) else raw.value if isinstance(raw, Binding) else raw)
        function.data = Closure(node, plan, tuple(captures), parameter_types, return_type)
        return function

    def execute_user(self, request):
        function, arguments, call = request.function, request.arguments, request.node
        closure = function.data
        self.check("call_depth", self.call_depth + 1, call)
        previous = self.frame
        try:
            # Argument expressions have all completed before any type check.
            for annotation, value, expression in zip(closure.parameter_types, arguments, call.children[1:]):
                self.typecheck(annotation, value, expression)
            with self.reserve(call, runtime_slots=len(closure.plan.locals) + 1):
                frame = Frame(function)
                self.frame = frame
                self.call_depth += 1
                try:
                    for parameter, value, annotation in zip(closure.parameters, arguments, closure.parameter_types):
                        self.define(id(parameter), value, annotation, parameter)
                    value, site, implicit = NULL, closure.node, True
                    try:
                        if closure.node.kind == "lambda":
                            value = (yield from self.evaluate(closure.node.children[-1]))
                            site, implicit = closure.node.children[-1], False
                        else:
                            (yield from self.block(closure.node.children[-1]))
                    except ReturnSignal as returned:
                        value, site, implicit = returned.value, returned.node, False
                    self.typecheck(closure.return_type, value, site, token_only=implicit)
                    return value
                finally:
                    frame.clear()
                    self.frame = previous
                    self.call_depth -= 1
        except (DiagnosticError, ResourceExceeded) as error:
            position = call.token.span.start
            note = f"调用 {closure.name}：{self.location(call)}:{position.line}:{position.column}"
            diagnostic = replace(error.diagnostic, notes=(*error.diagnostic.notes, note))
            if isinstance(error, ResourceExceeded):
                # Keep quota aborts outside ordinary language-error handlers.
                error.diagnostic = diagnostic
                raise
            raise DiagnosticError(diagnostic, error.phase) from None

    def lookup(self, symbol, node):
        for scope in reversed(self.scopes):
            if symbol in scope:
                return scope[symbol]
        if isinstance(symbol, str):
            reservation = self.reserve(node, runtime_objects=1, runtime_slots=1)
            value = Value("Namespace", {}) if symbol in NAMESPACES else Value("Function", FUNCTIONS[symbol])
            if value.kind == "Namespace":
                value.namespace = symbol
            value.reservation = reservation
            self.bindings[symbol] = Binding(value, False)
            return self.bindings[symbol]
        raise AssertionError("resolved binding missing")

    @contextmanager
    def scope(self, initial=None):
        scope = initial or {}
        old_slots = self.slots
        self.slots = []
        self.scopes.append(scope)
        try:
            yield
        finally:
            scope.clear()
            self.scopes.pop()
            for slot in self.slots:
                slot.release()
            self.slots = old_slots

    def block(self, node, initial=None):
        if self.frame is None:
            with self.scope(initial):
                for statement in node.children:
                    (yield from self.statement(statement))
        else:
            frame = self.frame
            try:
                for symbol, binding in (initial or {}).items():
                    self.define(symbol, binding.value, binding.annotation, node)
                for statement in node.children:
                    (yield from self.statement(statement))
            finally:
                for index in frame.function.data.plan.blocks[id(node)]:
                    frame.locals[index] = None
                    frame.annotations[index] = None

    def annotation(self, token, node):
        if token is None:
            return None
        resolved = self.program.annotations[id(token[0] if isinstance(token, tuple) else token)]
        if isinstance(resolved, str):
            return resolved
        symbol, fields = resolved
        value = self.read_reference(symbol, node)
        for name in fields:
            value = self.field(value, name, node)
        if value.kind not in {"Definition", "MachineDefinition"}:
            self.error(node, "E201", "类型注解需要结构定义")
        return value

    def typecheck(self, annotation, value, node, *, token_only=False):
        valid = (annotation is None or
                 isinstance(annotation, str) and value.kind == annotation or
                 isinstance(annotation, Value) and value.kind in {"Shape", "Machine"} and value.data[0] is annotation)
        if not valid:
            name = annotation if isinstance(annotation, str) else annotation.data[0].token.lexeme
            raise DiagnosticError(Diagnostic(f"注解要求 {name}，实际为 {value.kind}",
                                             "E201", self.location(node), node.token.span if token_only else node.span), Phase.EXECUTION)

    def statement(self, node):
        self.meter.cancellation.check()
        if node.kind == "use":
            root = self.program.modules[id(node)]
            if id(root) not in self.modules:
                exports = [n for n in root.children if n.kind in {"function", "shape", "machine"}]
                module = Value("Module", {}, self.reserve(node, runtime_objects=1, runtime_slots=len(exports)))
                self.modules[id(root)] = module
                for statement in root.children:
                    if statement.kind != "spec":
                        yield from self.statement(statement)
                module.data.update((n.token.lexeme, self.bindings[id(n)].value) for n in exports)
            self.bindings[id(node)] = Binding(self.modules[id(root)], False)
            self.slots.append(self.reserve(node, runtime_slots=1))
        elif node.kind == "match":
            yield from self.match(node)
        elif node.kind in {"assert", "trace"}:
            value = yield from self.evaluate(node.children[0])
            if node.kind == "trace":
                self.trace(value, node)
            else:
                self.typecheck("Bool", value, node.children[0])
                if not value.data:
                    self.error(node, "E210", "断言失败")
        elif node.kind == "machine":
            edges, states = self.program.machines[id(node)]
            value = Value("MachineDefinition", (node, edges, states), self.reserve(node, runtime_objects=1))
            slot = self.reserve(node, runtime_slots=1)
            self.scopes[-1][id(node)] = Binding(value, False)
            self.slots.append(slot)
        elif node.kind == "function":
            slot = self.reserve(node, runtime_slots=1) if self.frame is None else None
            try:
                self.define(id(node), self.make_function(node), None, node)
                if slot:
                    self.slots.append(slot)
            except BaseException:
                if slot:
                    slot.release()
                raise
        elif node.kind == "return":
            expression = node.children[0] if node.children else node
            value = (yield from self.evaluate(expression)) if node.children else NULL
            raise ReturnSignal(value, expression)
        elif node.kind == "binding":
            mutable, annotation = node.data
            slot = self.reserve(node, runtime_slots=1) if self.frame is None else None
            try:
                kind = self.annotation(annotation, node)
                value = (yield from self.evaluate(node.children[0]))
                self.typecheck(kind, value, node.children[0])
                self.define(id(node), value, kind, node)
                if slot:
                    self.slots.append(slot)
            except BaseException:
                if slot:
                    slot.release()
                raise
        elif node.kind == "shape":
            definition = Value("Definition", None, self.reserve(node, runtime_objects=1))
            slot = self.reserve(node, runtime_slots=1)
            self.scopes[-1][id(node)] = Binding(definition, False)
            self.slots.append(slot)
            types = {field.token.lexeme: self.annotation(field.data, field) for field in node.children}
            # Symbols bind lexically during prepare. Top-level definitions outlive
            # all block evaluations, so defaults can use these binding identities.
            definition.data = (node, types)
        elif node.kind == "assignment":
            target, expression = node.children
            if target.kind == "name":
                reference = self.program.references[id(target)]
                raw = self.raw_reference(reference, target)
                info = self.program.symbols.get(reference.symbol)
                if info is None or not info.mutable:
                    self.error(target, "E203", f"名称 {target.data} 不允许重新绑定")
                annotation = raw.annotation if isinstance(raw, Binding) else self.frame.annotations[reference.key]
                value = (yield from self.evaluate(expression))
                self.typecheck(annotation, value, expression)
                if isinstance(raw, Binding):
                    raw.value = value
                else:
                    self.frame.locals[reference.key] = value
            elif target.kind == "field":
                owner = (yield from self.evaluate(target.children[0]))
                self.field(owner, target.data, target, write=True)
                value = (yield from self.evaluate(expression))
                self.typecheck(owner.data[0].data[1][target.data], value, expression)
                owner.data[1][target.data] = value
            else:
                owner = (yield from self.evaluate(target.children[0]))
                index = (yield from self.evaluate(target.children[1]))
                self.index(owner, index, target, write=True)
                value = (yield from self.evaluate(expression))
                owner.replace(index.data, value, self, target)
        elif node.kind == "block":
            (yield from self.block(node))
        elif node.kind == "if":
            for index in range(0, len(node.children), 2):
                child = node.children[index]
                if child.kind == "block":
                    (yield from self.block(child))
                    break
                if self.condition((yield from self.evaluate(child)), child):
                    (yield from self.block(node.children[index + 1]))
                    break
        elif node.kind == "while":
            while self.condition((yield from self.evaluate(node.children[0])), node.children[0]):
                try:
                    (yield from self.block(node.children[1]))
                except LoopSignal as signal:
                    if signal.kind == "break":
                        break
        elif node.kind == "for":
            (yield from self.for_loop(node))
        elif node.kind in {"break", "continue"}:
            raise LoopSignal(node.kind)
        else:
            (yield from self.evaluate(node.children[0]))

    def condition(self, value, node):
        self.typecheck("Bool", value, node)
        return value.data

    def for_loop(self, node):
        iterable = (yield from self.evaluate(node.children[0]))
        if iterable.kind not in {"Array", "String", "Range"}:
            self.error(node, "E201", "for 需要 Array、String 或 Range")
        if iterable.kind == "Array":
            iterable.active += 1
        try:
            if iterable.kind == "Range":
                start, stop, step = iterable.data
                iterator = range(start.data, stop.data, step.data)
            else:
                iterator = iterable.data
            for item in iterator:
                self.meter.cancellation.check()
                with self.reserve(node, runtime_slots=1) if self.frame is None else nullcontext():
                    value = item if iterable.kind == "Array" else self.scalar(
                        "String" if iterable.kind == "String" else "Int", item, node)
                    try:
                        (yield from self.block(node.children[1], {id(node): Binding(value, False)}))
                    except LoopSignal as signal:
                        if signal.kind == "break":
                            break
        finally:
            if iterable.kind == "Array":
                iterable.active -= 1

    def field(self, owner, name, node, write=False):
        if write and getattr(owner, "frozen", False):
            self.error(node, "E203", "冻结对象只读")
        if owner.kind == "Machine":
            if name != "state":
                self.error(node, "E204", "状态机不存在该属性")
            if write:
                self.error(node, "E203", "state 只读")
            return owner.data[1]
        if owner.kind == "Module":
            if write:
                self.error(node, "E203", "模块导出只读")
            if name not in owner.data:
                self.error(node, "E303", f"模块没有导出 {name}")
            return owner.data[name]
        if owner.kind == "Namespace":
            if write:
                self.error(node, "E203", "命名空间字段只读")
            if name not in owner.data:
                namespace = owner.namespace
                if namespace == "array" and name == "Stats":
                    owner.data[name] = self.stats_definition(node)
                    return owner.data[name]
                qualified = namespace + "." + name
                if qualified not in FUNCTIONS:
                    self.error(node, "E302", f"字段 {name} 尚未实现或不存在")
                owner.data[name] = Value("Function", FUNCTIONS[qualified],
                                         self.reserve(node, runtime_objects=1, runtime_slots=1))
            return owner.data[name]
        if owner.kind != "Shape":
            self.error(node, "E201", "此值不支持字段访问或写入")
        if name not in owner.data[1]:
            self.error(node, "E302", f"结构字段 {name} 不存在")
        return owner.data[1][name]

    def index(self, owner, index, node, write=False):
        if owner.kind not in {"Array", "String"}:
            self.error(node, "E201", "此值不支持下标")
        if index.kind != "Int":
            self.error(node, "E201", "下标必须为 Int，不接受 Bool")
        if write and owner.kind == "String":
            self.error(node, "E203", "String 下标只读")
        if index.data < 0 or index.data >= len(owner.data):
            self.error(node, "E204", "下标越界")
        return owner.data[index.data] if owner.kind == "Array" else self.scalar("String", owner.data[index.data], node)

    def evaluate(self, node):
        self.meter.cancellation.check()
        kind = node.kind
        if kind == "current":
            return self.current_item
        if kind == "query":
            return (yield from self.query_value(node))
        if kind == "pipe":
            value = yield from self.evaluate(node.children[0])
            call = node.children[1]
            function = yield from self.evaluate(call.children[0])
            with self.reserve(call, runtime_slots=len(call.children) - 1):
                arguments = []
                for arg in call.children[1:]:
                    arguments.append(value if arg.kind == "current" else (yield from self.evaluate(arg)))
                return (yield from self.call_value(function, arguments, call))
        if kind == "quantity":
            number, dimensions = self.program.quantities[id(node)]
            return quantities.value(self, number, dimensions, node)
        if kind == "result":
            payload = yield from self.evaluate(node.children[0])
            return self.result(node.data == "SUCCESS", payload, node.children[0])
        if kind == "propagate":
            value = yield from self.evaluate(node.children[0])
            self.typecheck("Result", value, node.children[0])
            if not value.data[0]:
                raise ReturnSignal(value, node)
            return value.data[1]
        if kind == "send":
            left = yield from self.evaluate(node.children[0])
            right = yield from self.evaluate(node.children[1])
            return self.send(left, right, node)
        if kind == "lazy":
            value = self.make_function(node)
            value.kind, value.state, value.cached = "Lazy", "NEW", None
            value.owners.append(self.reserve(node, runtime_slots=1))
            return value
        if kind == "lambda":
            return self.make_function(node)
        if kind in {"integer", "float"}:
            return self.scalar("Int" if kind == "integer" else "Float", self.program.integers[id(node)], node)
        if kind == "string":
            return self.scalar("String", node.data, node)
        if kind == "bool":
            return boolean(node.data)
        if kind == "null":
            return NULL
        if kind == "name":
            return self.read_reference(self.program.references[id(node)], node)
        if kind == "group":
            return (yield from self.evaluate(node.children[0]))
        if kind == "field":
            return self.field((yield from self.evaluate(node.children[0])), node.data, node)
        if kind == "index":
            owner = (yield from self.evaluate(node.children[0]))
            return self.index(owner, (yield from self.evaluate(node.children[1])), node)
        if kind == "array":
            self.check("container_items", len(node.children), node)
            value = Array(self, node)
            for child in node.children:
                value.push((yield from self.evaluate(child)), self, child)
            return value
        if kind in {"construct", "with"}:
            return (yield from self.construct(node))
        if kind == "unary":
            value = (yield from self.evaluate(node.children[0]))
            if node.token.kind == "NOT":
                if value.kind != "Bool":
                    self.error(node, "E201", "not 需要 Bool")
                return boolean(not value.data)
            if value.kind == "Quantity" and node.token.kind in {"PLUS", "MINUS"}:
                number, dimensions = value.data
                return quantities.value(self, number if node.token.kind == "PLUS" else -number, dimensions, node)
            if value.kind not in {"Int", "Float"}:
                self.error(node, "E201", "一元正负号需要普通数值")
            if node.token.kind == "PLUS":
                return value
            size = 8 if value.kind == "Float" else (value.data.bit_length() + 7) // 8
            reservation = self.reserve(node, runtime_payload_bytes=size)
            return Value(value.kind, -value.data, reservation)
        if kind in {"add", "binary"}:
            left = (yield from self.evaluate(node.children[0]))
            operation = node.token.kind
            if operation in {"AND", "OR"}:
                test = self.condition(left, node.children[0])
                if operation == "AND" and not test or operation == "OR" and test:
                    return boolean(test)
                return boolean(self.condition((yield from self.evaluate(node.children[1])), node.children[1]))
            right = (yield from self.evaluate(node.children[1]))
            return self.binary(operation, left, right, node)
        if kind == "call":
            function = (yield from self.evaluate(node.children[0]))
            with self.reserve(node, runtime_slots=len(node.children) - 1):
                arguments = []
                for arg in node.children[1:]:
                    arguments.append((yield from self.evaluate(arg)))
                return (yield from self.call_value(function, arguments, node))
        raise AssertionError(f"unknown expression node: {kind}")

    def construct(self, node):
        base = (yield from self.evaluate(node.children[0]))
        expected = "Shape" if node.kind == "with" else "Definition"
        if base.kind != expected:
            self.error(node, "E201", "构造需要结构定义；with 需要结构实例")
        definition = base.data[0] if node.kind == "with" else base
        declaration, types = definition.data
        explicit = set()
        for field in node.children[1:]:
            if field.data not in types or field.data in explicit:
                self.error(field, "E203", "未知或重复的结构字段")
            explicit.add(field.data)
        if node.kind == "construct":
            for field in declaration.children:
                if field.token.lexeme not in explicit and not field.children:
                    self.error(node, "E203", f"缺少必填字段 {field.token.lexeme}")
        result = Value("Shape", None, self.reserve(node, runtime_objects=1, runtime_slots=len(types) + 1))
        # Reserve field slots once and populate in declaration order. Pending
        # fields are private to this construction and cannot be observed.
        fields = {name: NULL for name in types}
        result.data = (definition, fields)
        for field in node.children[1:]:
            value = (yield from self.evaluate(field.children[0]))
            self.typecheck(types[field.data], value, field.children[0])
            fields[field.data] = value
        for field in declaration.children:
            name = field.token.lexeme
            if name not in explicit:
                if node.kind == "with":
                    fields[name] = base.data[1][name]
                else:
                    value = (yield from self.evaluate(field.children[0]))
                    self.typecheck(types[name], value, field.children[0])
                    fields[name] = value
        return result

    def make_range(self, args, node):
        for index, value in enumerate(args):
            if value.kind != "Int":
                if node.kind == "call":
                    self.typecheck("Int", value, node.children[index + 1])
                self.error(node, "E201", "区间边界需要 Int")
        if not args[2].data:
            self.error(node, "E208", "Range 步长不能为零")
        return Value("Range", tuple(args), self.reserve(node, runtime_objects=1, runtime_slots=3))

    def binary(self, operation, left, right, node):
        if operation in {"EQUAL", "NOT_EQUAL"}:
            depth = 0
            while left.kind == right.kind == "Result":
                depth += 1
                self.check("value_depth", depth, node)
                if left.data[0] != right.data[0]:
                    return boolean(operation == "NOT_EQUAL")
                left, right = left.data[1], right.data[1]
            if left.kind == right.kind == "Quantity":
                equal = left.data == right.data
                return boolean(equal if operation == "EQUAL" else not equal)
        elif "Quantity" in {left.kind, right.kind}:
            if operation not in {"PLUS", "MINUS", "MULTIPLY", "DIVIDE", "LESS", "LESS_EQUAL", "GREATER", "GREATER_EQUAL"} or any(v.kind not in {"Int", "Float", "Quantity"} for v in (left, right)):
                self.error(node, "E201", "数量不支持此运算或类型")
            return quantities.calculate(self, operation, left, right, node)
        numeric = left.kind in {"Int", "Float"} and right.kind in {"Int", "Float"}
        if operation in {"EQUAL", "NOT_EQUAL"}:
            if numeric or left.kind == right.kind and left.kind in {"String", "Bool", "Null"}:
                equal = left.data == right.data
            elif left.kind == right.kind == "Range":
                equal = tuple(v.data for v in left.data) == tuple(v.data for v in right.data)
            else:
                equal = left is right
            return boolean(equal if operation == "EQUAL" else not equal)
        if operation in {"LESS", "LESS_EQUAL", "GREATER", "GREATER_EQUAL"}:
            if not numeric and not left.kind == right.kind == "String":
                self.error(node, "E201", "排序比较需要两个普通数或两个 String")
            function = {"LESS": operator.lt, "LESS_EQUAL": operator.le,
                        "GREATER": operator.gt, "GREATER_EQUAL": operator.ge}[operation]
            return boolean(function(left.data, right.data))
        if operation == "INTERVAL":
            return self.make_range((left, right, self.scalar("Int", 1, node)), node)
        if operation == "PLUS" and left.kind == right.kind == "String":
            size = len(left.data) + len(right.data)
            self.check("text_codepoints", size, node)
            reservation = self.reserve(node, runtime_payload_bytes=4 * size)
            return Value("String", left.data + right.data, reservation)
        if not numeric or operation in {"FLOOR_DIVIDE", "REMAINDER"} and not left.kind == right.kind == "Int":
            self.error(node, "E201", "此算术运算的数值类型不匹配；不隐式转换 Bool/String")
        if operation in {"DIVIDE", "FLOOR_DIVIDE", "REMAINDER"} and right.data == 0:
            self.error(node, "E205", "除数不能为零")
        if left.kind == right.kind == "Int" and operation != "DIVIDE":
            return self.integer_operation(operation, left.data, right.data, node)
        try:
            # Explicit promotion is required even for Int / Int.
            a, b = float(left.data), float(right.data)
            result = {"PLUS": operator.add, "MINUS": operator.sub,
                      "MULTIPLY": operator.mul, "DIVIDE": operator.truediv}[operation](a, b)
        except OverflowError:
            self.error(node, "E208", "必要的 Float 提升超范围")
        return self.scalar("Float", result, node)

    def integer_operation(self, operation, left, right, node):
        if operation == "PLUS" and left >= 0 and right >= 0:
            scratch = (max(left.bit_length(), right.bit_length()) + 7) // 8
            with self.reserve(node, runtime_payload_bytes=scratch):
                bits = self.add_bits(left, right)
            self.check("integer_bits", bits, node)
            reservation = self.reserve(node, runtime_payload_bytes=(bits + 7) // 8)
            return Value("Int", left + right, reservation)
        if operation in {"PLUS", "MINUS"}:
            other = right if operation == "PLUS" else -right
            if left == -other:
                return self.scalar("Int", 0, node)
            a, b = abs(left), abs(other)
            with self.reserve(node, runtime_payload_bytes=(max(a.bit_length(), b.bit_length()) + 7) // 8):
                bits = self.add_bits(a, b) if (left < 0) == (other < 0) else self.difference_bits(max(a, b), min(a, b))
            self.check("integer_bits", bits, node)
            reservation = self.reserve(node, runtime_payload_bytes=(bits + 7) // 8)
            return Value("Int", left + other, reservation)
        if operation == "MULTIPLY":
            if not left or not right:
                return self.scalar("Int", 0, node)
            width = left.bit_length() + right.bit_length()
            upper = (width + 7) // 8
            available = self.meter.policy.limits["runtime_payload_bytes"] - self.meter.used("runtime_payload_bytes")
            if width - 1 > self.meter.policy.limits["integer_bits"]:
                self.check("integer_bits", width - 1, node)
            if width > self.meter.policy.limits["integer_bits"] or upper > available:
                # Upper bounds alone must not reject an in-budget product.
                with self.reserve(node, runtime_payload_bytes=(max(left.bit_length(), right.bit_length()) + 7) // 8):
                    width = self.product_bits(abs(left), abs(right))
                self.check("integer_bits", width, node)
                upper = (width + 7) // 8
            reservation = self.reserve(node, runtime_payload_bytes=upper)
            try:
                result = left * right
                self.check("integer_bits", result.bit_length(), node)
                # Transfer ownership from the bounded host result to its exact payload.
                reservation.release()
                return self.scalar("Int", result, node)
            except BaseException:
                reservation.release()
                raise
        # Integer quotient and remainder never exceed the operands' widths.
        # This reservation owns the bounded host result until it is transferred.
        width = max(left.bit_length(), right.bit_length())
        reservation = self.reserve(node, runtime_payload_bytes=(width + 7) // 8)
        try:
            result = left // right if operation == "FLOOR_DIVIDE" else left % right
            self.check("integer_bits", result.bit_length(), node)
            reservation.release()
            return self.scalar("Int", result, node)
        except BaseException:
            reservation.release()
            raise

    def difference_bits(self, larger, smaller):
        borrow = bits = 0
        for shift in range(0, larger.bit_length(), 8):
            self.meter.cancellation.check()
            chunk = ((larger >> shift) & 255) - ((smaller >> shift) & 255) - borrow
            borrow = int(chunk < 0)
            chunk &= 255
            if chunk:
                bits = shift + chunk.bit_length()
        return bits

    def product_bits(self, left, right):
        """Exact product width using streamed base-256 convolution, no product buffer."""
        a, b = (left.bit_length() + 7) // 8, (right.bit_length() + 7) // 8
        carry = bits = 0
        for place in range(a + b):
            self.meter.cancellation.check()
            digit = carry
            for index in range(max(0, place - b + 1), min(a, place + 1)):
                self.meter.cancellation.check()
                digit += ((left >> (index * 8)) & 255) * ((right >> ((place - index) * 8)) & 255)
            carry = digit >> 8
            if digit & 255:
                bits = place * 8 + (digit & 255).bit_length()
        return bits

    def call(self, name, args, node):
        name = name.removeprefix("core.")
        if name == "io.print":
            return self.print_value(args[0], node)
        if name == "io.input":
            return self.input_value(args[0], node)
        if name == "range":
            return self.make_range(args, node)
        value = args[0]
        if name == "len":
            if value.kind not in {"String", "Array", "Map", "Range"}:
                self.error(node, "E201", "len 需要 Array、String 或 Range")
            if value.kind == "Range":
                start, stop, step = (item.data for item in value.data)
                length = max(0, (stop - start + step - (1 if step > 0 else -1)) // step)
            else:
                length = len(value.data)
            return self.scalar("Int", length, node)
        if name == "str":
            if value.kind not in {"Int", "Float", "String", "Bool", "Null", "Quantity"}:
                self.error(node, "E201", "str 仅接受基础标量")
            if value.kind == "String":
                return value
            return self.text_value(value, node)
        self.typecheck("Array", value, node.children[1])
        if name == "array.push":
            value.push(args[1], self, node)
            return NULL
        if name == "array.pop":
            return value.pop(self, node)
        if name == "array.copy":
            result = Array(self, node)
            for item in value.data:
                result.push(item, self, node)
            return result
        raise AssertionError("unregistered native implementation")

    def input_value(self, prompt, node):
        self.typecheck("String", prompt, node.children[1])
        self.output.write(prompt.data)
        parts, reservations = [], []
        count = byte_count = 0
        pending_cr = False

        def append(character):
            nonlocal count
            count += 1
            self.check("text_codepoints", count, node)
            reservations.append(self.reserve(node, runtime_payload_bytes=4))
            parts.append(character)

        try:
            while True:
                self.meter.cancellation.check()
                try:
                    character = self.stdin.read(1)
                except (OSError, UnicodeError):
                    self.error(node, "E401", "无法读取严格 UTF-8 标准输入")
                byte_count += len(character.encode("utf-8"))
                self.check("io_payload_bytes", byte_count, node)
                if character == "\n":
                    break
                if pending_cr:
                    append("\r")
                    pending_cr = False
                if not character:
                    if not parts:
                        return NULL
                    break
                if character == "\r":
                    pending_cr = True
                else:
                    append(character)
            reservation = self.reserve(node, runtime_payload_bytes=4 * count)
            return Value("String", "".join(parts), reservation)
        finally:
            for reservation in reservations:
                reservation.release()

    def scalar_text(self, value, node):
        if value.kind == "String":
            return value.data
        if value.kind == "Bool":
            return "true" if value.data else "false"
        if value.kind == "Null":
            return "null"
        if value.kind == "Float":
            return str(value.data)
        raise AssertionError("Int formatting requires a reserved text value")

    def text_value(self, value, node):
        if value.kind == "Quantity":
            return quantities.text(self, value, node)
        if value.kind != "Int":
            return self.scalar("String", self.scalar_text(value, node), node)
        with self.reserve(node, runtime_payload_bytes=(value.data.bit_length() + 7) // 8):
            remaining, digits = abs(value.data), 0
            while remaining >= 1_000_000_000:
                self.meter.cancellation.check()
                remaining //= 1_000_000_000
                digits += 9
            digits += len(str(remaining))
        self.check("numeric_digits", digits, node)
        digits += value.data < 0
        self.check("text_codepoints", digits, node)
        reservation = self.reserve(node, runtime_payload_bytes=4 * digits)
        return Value("String", str(value.data), reservation)

    def debug_text(self, value, node):
        parts, owners, active = [], [], set()
        count = 0

        def append(text):
            nonlocal count
            count += len(text)
            self.check("text_codepoints", count, node)
            owners.append(self.reserve(node, runtime_payload_bytes=4 * len(text)))
            parts.append(text)

        def visit(item, depth):
            if id(item) in active:
                append("<cycle>")
                return
            if item.kind == "Int":
                formatted = self.text_value(item, node)
                append(formatted.data)
            elif item.kind in {"Float", "String", "Bool", "Null"}:
                append(self.scalar_text(item, node))
            elif item.kind == "Quantity":
                append(quantities.text(self, item, node).data)
            elif item.kind == "Lazy":
                append(f"<lazy {item.state}>")
            elif item.kind == "MachineDefinition":
                append("<machine " + item.data[0].token.lexeme + ">")
            elif item.kind == "Machine":
                append("<machine " + item.data[0].data[0].token.lexeme + ": " + item.data[1].data + ">")
            elif item.kind == "Function":
                append(f"<function {item.data.name}>")
            elif item.kind == "Module":
                append("<module>")
            elif item.kind == "Namespace":
                append("<module " + item.namespace + ">")
            elif item.kind == "Definition":
                append("<shape " + item.data[0].token.lexeme + ">")
            else:
                self.check("value_depth", depth + 1, node)
                active.add(id(item))
                try:
                    if item.kind == "Result":
                        append("(^_^)(" if item.data[0] else "(T_T)(")
                        visit(item.data[1], depth + 1)
                        append(")")
                    elif item.kind == "Map":
                        append("{")
                        for index, (key, child) in enumerate(item.data.items()):
                            if index:
                                append(", ")
                            append(key + ": ")
                            visit(child, depth + 1)
                        append("}")
                    elif item.kind == "Array":
                        append("[")
                        for index, child in enumerate(item.data):
                            if index:
                                append(", ")
                            visit(child, depth + 1)
                        append("]")
                    elif item.kind == "Range":
                        append("range(")
                        for index, child in enumerate(item.data):
                            if index:
                                append(", ")
                            visit(child, depth + 1)
                        append(")")
                    else:
                        append(item.data[0].data[0].token.lexeme + "::{")
                        for index, (name, child) in enumerate(item.data[1].items()):
                            if index:
                                append(", ")
                            append(name + ": ")
                            visit(child, depth + 1)
                        append("}")
                finally:
                    active.remove(id(item))
        try:
            visit(value, 0)
            reservation = self.reserve(node, runtime_payload_bytes=4 * count)
            return Value("String", "".join(parts), reservation)
        finally:
            for owner in owners:
                owner.release()

    def add_bits(self, left, right):
        """Exact nonnegative sum width without allocating the result first.

        Scan bounded byte chunks for the final carry, with reserved shift scratch.
        This avoids rejecting a result merely because an upper bound is too large.
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
                remaining, digits = abs(value.data), 0
                while remaining >= 1_000_000_000:
                    self.meter.cancellation.check()
                    remaining //= 1_000_000_000
                    digits += 9
                digits += len(str(remaining))
            self.check("numeric_digits", digits, node)
            digits += value.data < 0
            self.check("text_codepoints", digits, node)
            # str(Int) and its LF-appended copy coexist during concatenation.
            with self.reserve(node, runtime_payload_bytes=4 * (2 * digits + 1)):
                self.output.write(str(value.data) + "\n")
            return NULL
        elif value.kind == "String":
            text = value.data
        elif value.kind in {"Null", "Bool", "Float"}:
            text = self.scalar_text(value, node)
        elif value.kind == "Function":
            text = f"<function {value.data.name}>"
        elif value.kind == "Namespace":
            text = "<module " + value.namespace + ">"
        else:
            formatted = self.debug_text(value, node)
            text = formatted.data
        self.check("text_codepoints", len(text), node)
        # Formatting and the appended LF are bounded temporary text payloads.
        with self.reserve(node, runtime_payload_bytes=4 * (len(text) + 1)):
            self.output.write(text + "\n")
        return NULL
