"""P04 AST operations, isolated query state and explicit Lazy activation."""
from dataclasses import replace
from functools import cmp_to_key

from .diagnostics import Diagnostic, DiagnosticError, Phase, ResourceExceeded
from .values import Array, Binding, Frame, NULL, ReturnSignal, Value, WakeRequest, boolean
from . import quantities


class Features:
    def result(self, success, payload, node):
        if not success:
            self.typecheck("String", payload, node)
        return Value("Result", (success, payload), self.reserve(node, runtime_slots=1))

    def trace(self, value, node):
        formatted = self.debug_text(value, node)
        self.output.diagnostic(Diagnostic(formatted.data, file=self.file, span=node.children[0].span,
                                          kind="trace"))

    def match(self, node):
        value = yield from self.evaluate(node.children[0])
        for arm in node.children[1:]:
            pattern, body = arm.children
            initial = None
            if pattern.kind == "wildcard":
                matches = True
            elif pattern.kind == "payload_pattern":
                matches = value.kind == "Result" and value.data[0] == (pattern.data == "SUCCESS")
                if matches:
                    initial = {id(pattern): Binding(value.data[1], False)}
            else:
                expected = yield from self.evaluate(pattern.children[0])
                matches = self.binary("EQUAL", value, expected, pattern).data
            if matches:
                if initial and self.frame is None:
                    with self.reserve(pattern, runtime_slots=1):
                        yield from self.block(body, initial)
                else:
                    yield from self.block(body, initial)
                return
        self.error(node, "E207", "匹配没有覆盖当前值")

    def call_value(self, function, arguments, node):
        if function.kind == "MachineDefinition":
            if len(arguments) != 1:
                self.error(node, "E202", "状态机构造需要一个参数")
            self.typecheck("String", arguments[0], node.children[1])
            if arguments[0].data not in function.data[2]:
                self.error(node.children[1], "E212", "未知初始状态")
            return Value("Machine", [function, arguments[0]], self.reserve(node, runtime_objects=1, runtime_slots=2))
        if function.kind != "Function":
            self.error(node, "E202", "此值不可调用")
        if len(arguments) != len(function.data.parameters):
            self.error(node, "E202", f"{function.data.name} 参数数量不符")
        from .values import Closure, CallRequest
        if isinstance(function.data, Closure):
            handoff = yield CallRequest(function, arguments, node)
            return handoff.pop()
        if function.data.name == "core.wake":
            self.typecheck("Lazy", arguments[0], node.children[1])
            handoff = yield WakeRequest(arguments[0], node)
            return handoff.pop()
        return self.call(function.data.name, arguments, node)

    def execute_lazy(self, request):
        value, node = request.value, request.node
        position = node.token.span.start
        note = f"wake：{self.file}:{position.line}:{position.column}"
        if value.state == "READY":
            return value.cached
        if value.state == "FAILED":
            raise DiagnosticError(replace(value.cached, notes=(*value.cached.notes, note)), Phase.EXECUTION)
        if value.state == "RUNNING":
            self.error(node, "E209", "循环唤醒 Lazy")
        self.check("call_depth", self.call_depth + 1, node)
        previous = self.frame
        with self.reserve(node, runtime_slots=len(value.data.plan.locals) + 1):
            frame = Frame(value)
            self.frame, value.state = frame, "RUNNING"
            self.call_depth += 1
            try:
                result = yield from self.evaluate(value.data.node.children[0])
                value.cached, value.state = result, "READY"
                return result
            except DiagnosticError as error:
                value.cached, value.state = error.diagnostic, "FAILED"
                raise DiagnosticError(replace(error.diagnostic, notes=(*error.diagnostic.notes, note)), error.phase) from None
            except BaseException:
                value.cached, value.state = None, "NEW"
                raise
            finally:
                frame.clear()
                self.frame = previous
                self.call_depth -= 1

    def send(self, left, right, node):
        self.typecheck("Machine", left, node.children[0])
        self.typecheck("String", right, node.children[1])
        if getattr(left, "frozen", False):
            self.error(node, "E203", "冻结状态机不可发送事件")
        definition, state = left.data
        target = definition.data[1].get((state.data, right.data))
        if target is None:
            text = quantities.join_text(self, ("invalid transition: ", state.data, " -- ", right.data), node)
            return self.result(False, text, node)
        state = self.scalar("String", target, node)
        result = self.result(True, state, node)
        left.data[1] = state
        return result

    def query_value(self, node):
        source = yield from self.evaluate(node.children[0])
        self.typecheck("Array", source, node.children[0])
        count = len(source.data)
        clauses = {clause.kind: clause for clause in node.children[1:]}
        previous = self.current_item
        # Snapshot, retained indices, keys and sorting workspace are separately
        # accounted before allocation. No callbacks run during the sort itself.
        with self.reserve(node, runtime_slots=count):
            snapshot = tuple(source.data)
            try:
                take = None
                if "take" in clauses:
                    expression = clauses["take"].children[0]
                    take_value = yield from self.evaluate(expression)
                    self.typecheck("Int", take_value, expression)
                    take = take_value.data
                    if take < 0:
                        self.error(expression, "E208", "take 不能为负数")
                with self.reserve(node, runtime_slots=count):
                    retained = []
                    for index, item in enumerate(snapshot):
                        self.meter.cancellation.check()
                        self.current_item = item
                        if "keep" in clauses:
                            expression = clauses["keep"].children[0]
                            keep = yield from self.query_expression(expression, index)
                            self.typecheck("Bool", keep, expression)
                            if not keep.data:
                                continue
                        retained.append(index)
                    if "order" in clauses:
                        clause = clauses["order"]
                        expression = clause.children[0]
                        with self.reserve(node, runtime_slots=3 * len(retained)):
                            keyed, category, dimensions = [], None, None
                            for index in retained:
                                self.current_item = snapshot[index]
                                key = yield from self.query_expression(expression, index)
                                kind = "number" if key.kind in {"Int", "Float"} else key.kind
                                if kind not in {"number", "String", "Quantity"} or category not in {None, kind}:
                                    self.error(expression, "E201", "查询排序键类别不一致或不支持")
                                if kind == "Quantity":
                                    if dimensions is not None and dimensions != key.data[1]:
                                        self.error(expression, "E213", "查询排序键量纲不一致")
                                    dimensions = key.data[1]
                                category = kind
                                keyed.append((index, key))
                            def compare(a, b):
                                self.meter.cancellation.check()
                                if self.binary("LESS", a[1], b[1], expression).data:
                                    return -1
                                if self.binary("GREATER", a[1], b[1], expression).data:
                                    return 1
                                return 0
                            keyed.sort(key=cmp_to_key(compare), reverse=clause.data == "DESC")
                            retained[:] = (index for index, key in keyed)
                            keyed.clear()
                            key = None
                    result = Array(self, node)
                    for offset, index in enumerate(retained):
                        if take is not None and offset >= take:
                            break
                        self.current_item = snapshot[index]
                        item = yield from self.query_expression(clauses["yield"].children[0], index)
                        result.push(item, self, clauses["yield"])
                    return result
            finally:
                self.current_item = previous

    def query_expression(self, expression, index):
        try:
            return (yield from self.evaluate(expression))
        except (DiagnosticError, ResourceExceeded) as error:
            error.diagnostic = replace(error.diagnostic,
                notes=(*error.diagnostic.notes, f"查询输入下标 {index}"))
            raise
