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
        if index < 0 or index >= len(self.data):
            runtime.error(node, "E204", "数组下标越界")
        self.data[index] = value
        self.content_version += 1


class LoopSignal(BaseException):
    def __init__(self, kind):
        self.kind = kind
