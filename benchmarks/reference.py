"""Python task wrappers, independently written; no AST execution or ZZY algorithms.

The library group shares only the resource policy/meter with ZZY. The comparison
includes validation and logical scratch/result ownership, not Python RSS limits.
"""
from fractions import Fraction
from functools import cmp_to_key
from math import gcd

from zzy.diagnostics import Phase
from zzy.resources import ResourceMeter, ResourcePolicy


def sum_bits(a, b, meter):
    width = max(a.bit_length(), b.bit_length())
    if not width:
        return 0
    carry = 0
    for shift in range(0, width, 8):
        meter.cancellation.check()
        chunk = ((a >> shift) & 255) + ((b >> shift) & 255) + carry
        carry = chunk >> 8
    return shift + 9 if carry else shift + (chunk & 255).bit_length()


class CheckedArray:
    def __init__(self, values, policy=None):
        self.values = values
        self.meter = ResourceMeter(policy or ResourcePolicy(), Phase.EXECUTION)
        self.meter.check('container_items', len(values))
        self.owners = [self.meter.reserve(runtime_objects=1, runtime_slots=len(values),
            runtime_payload_bytes=sum((abs(x).bit_length()+7)//8 for x in values if type(x) is int))]

    def sum(self):
        total = 0
        owner = self.meter.reserve(runtime_payload_bytes=0)
        try:
            for value in self.values:
                self.meter.cancellation.check()
                if type(value) is not int:
                    raise TypeError('sum requires Int, not Bool')
                # B04 is nonnegative. Reject other inputs instead of pretending
                # this benchmark-only wrapper implements the entire stdlib.
                if value < 0:
                    raise ValueError('B04 wrapper accepts nonnegative inputs only')
                with self.meter.reserve(runtime_payload_bytes=(max(total.bit_length(), value.bit_length())+7)//8):
                    bits = sum_bits(total, value, self.meter)
                self.meter.check('integer_bits', bits)
                next_owner = self.meter.reserve(runtime_payload_bytes=(bits+7)//8)
                total = total + value
                owner.release()
                owner = next_owner
            self.owners.append(owner)
            return total
        except BaseException:
            owner.release()
            raise

    def sorted(self):
        kind = type(self.values[0]) if self.values else None
        if kind not in (None, int, str) or any(type(x) is not kind for x in self.values):
            raise TypeError('sorted requires homogeneous Int or String')
        with self.meter.reserve(runtime_slots=3*len(self.values)):
            def key(x):
                self.meter.cancellation.check()
                return x
            ordered = sorted(self.values, key=key)
            self.owners.append(self.meter.reserve(runtime_objects=1))
            result = []
            for value in ordered:
                self.meter.check('container_items', len(result)+1)
                self.owners.append(self.meter.reserve(runtime_slots=1))
                result.append(value)
            return result

    def close(self):
        for owner in self.owners:
            owner.release()
        self.owners.clear()


def query(tasks, take=10):
    snapshot = tuple(tasks)
    if type(take) is not int or take < 0:
        raise TypeError('nonnegative Int take required')
    retained = []
    for index, task in enumerate(snapshot):
        if type(task['done']) is not bool:
            raise TypeError('Bool keep required')
        if not task['done']:
            retained.append(index)
    keyed = []
    for index in retained:
        key = snapshot[index]['priority']
        if type(key) is not int:
            raise TypeError('B07 keys must be Int')
        keyed.append((index, key))
    def compare(a, b):
        if a[1] < b[1]:
            return -1
        if a[1] > b[1]:
            return 1
        return 0
    keyed.sort(key=cmp_to_key(compare), reverse=True)
    retained[:] = (index for index, key in keyed)
    keyed.clear()
    return [snapshot[index]['id'] for index in retained[:take]]


class Machine:
    def __init__(self, graph, state):
        if state not in {s for edge in graph for s in (edge[0], graph[edge])}:
            raise ValueError('invalid initial state')
        self.graph, self.state = graph, state

    def send(self, event):
        if type(event) is not str:
            raise TypeError('String event required')
        target = self.graph.get((self.state, event))
        if target is None:
            return False, f'invalid transition: {self.state} -- {event}'
        result = (True, target)
        self.state = target
        return result


QUANTITY_POLICY = ResourcePolicy()


def quantity_add(left, right):
    a, ad = left
    b, bd = right
    if ad != bd:
        raise ValueError('incompatible dimensions')
    # Same gcd/cross-products/Fraction reduction, with intermediate bit checks.
    def checked(value):
        if abs(value).bit_length() > QUANTITY_POLICY.limits['integer_bits']:
            raise OverflowError('integer_bits')
        return value
    for number in (a, b):
        checked(number.numerator)
        checked(number.denominator)
    g = gcd(a.denominator, b.denominator)
    x = checked(a.numerator * (b.denominator // g))
    y = checked(b.numerator * (a.denominator // g))
    numerator = checked(x + y)
    denominator = checked(a.denominator * (b.denominator // g))
    number = Fraction(numerator, denominator)
    checked(number.numerator)
    checked(number.denominator)
    if any(abs(x) > QUANTITY_POLICY.limits['quantity_exponent_abs'] for x in ad):
        raise OverflowError('quantity_exponent_abs')
    return number, ad


def quantity_text(value):
    number, dimensions = value
    assert dimensions == (0, 1)
    return f'{number}::s'
