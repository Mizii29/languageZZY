"""Context-owned values and the single array mutation boundary."""

from dataclasses import dataclass


class Value:
    def __init__(self, kind, data, reservation=None):
        self.kind, self.data, self.reservation = kind, data, reservation
        self.owners = []

    def __del__(self):
        if getattr(self, "reservation", None) is not None:
            self.reservation.release()
        for owner in getattr(self, "owners", ()):
            owner.release()


NULL = Value("Null", None)
TRUE = Value("Bool", True)
FALSE = Value("Bool", False)


def boolean(value):
    return TRUE if value else FALSE


@dataclass
class Binding:
    value: Value
    mutable: bool
    annotation: object = None


class Array(Value):
    def __init__(self, runtime, node):
        super().__init__("Array", [], runtime.reserve(node, runtime_objects=1))
        self.active = 0
        self.structural_version = self.content_version = 0

    def writable(self, runtime, node):
        if getattr(self, "frozen", False):
            runtime.error(node, "E203", "冻结数组只读")
        if self.active:
            runtime.error(node, "E206", "活动遍历期间不能增删或重排数组")

    def push(self, value, runtime, node):
        self.writable(runtime, node)
        runtime.check("container_items", len(self.data) + 1, node)
        slot = runtime.reserve(node, runtime_slots=1)
        try:
            self.data.append(value)
            self.owners.append(slot)
        except BaseException:
            slot.release()
            raise
        self.structural_version += 1
        self.content_version += 1

    def pop(self, runtime, node):
        self.writable(runtime, node)
        if not self.data:
            runtime.error(node, "E204", "不能从空数组 pop")
        value = self.data.pop()
        self.owners.pop().release()
        self.structural_version += 1
        self.content_version += 1
        return value

    def replace(self, index, value, runtime, node):
        if getattr(self, "frozen", False):
            runtime.error(node, "E203", "冻结数组只读")
        if index < 0 or index >= len(self.data):
            runtime.error(node, "E204", "数组下标越界")
        self.data[index] = value
        self.content_version += 1


class LoopSignal(BaseException):
    def __init__(self, kind):
        self.kind = kind


class Cell(Binding):
    """Shared storage allocated only for a captured mutable binding."""
    def __init__(self, value, annotation, reservation):
        super().__init__(value, True, annotation)
        self.reservation = reservation

    def __del__(self):
        self.reservation.release()


@dataclass(frozen=True)
class Closure:
    node: object
    plan: object
    captures: tuple
    parameter_types: tuple
    return_type: object

    @property
    def name(self):
        return self.node.token.lexeme if self.node.kind == "function" else "<anonymous>"

    @property
    def parameters(self):
        return self.node.children[:-1]


class Frame:
    """Direct local slots; only selected entries contain Cells."""
    def __init__(self, function):
        self.function = function
        self.locals = [None] * len(function.data.plan.locals)
        self.annotations = [None] * len(self.locals)

    def clear(self):
        self.locals.clear()
        self.annotations.clear()


class ReturnSignal(BaseException):
    def __init__(self, value, node):
        self.value, self.node = value, node


@dataclass(frozen=True)
class CallRequest:
    function: Value
    arguments: list
    node: object


@dataclass(frozen=True)
class WakeRequest:
    value: Value
    node: object


def freeze(value, runtime, node):
    """Internal recursive freezing boundary; no new public language interface."""
    pending, seen = [(value, 0)], set()
    while pending:
        item, depth = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        if item.kind == "Result":
            runtime.check("value_depth", depth + 1, node)
            pending.append((item.data[1], depth + 1))
        if item.kind in {"Array", "Shape", "Machine"}:
            runtime.check("value_depth", depth + 1, node)
            item.frozen = True
            children = item.data if item.kind == "Array" else item.data[1].values() if item.kind == "Shape" else ()
            pending.extend((child, depth + 1) for child in children)
