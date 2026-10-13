"""Exact quantities with checked intermediate integer arithmetic."""
from fractions import Fraction
from math import gcd, log2
from types import MappingProxyType

from .values import Value, boolean

UNITS = MappingProxyType({
    "ms": (Fraction(1, 1000), (0, 1)), "s": (Fraction(1), (0, 1)),
    "min": (Fraction(60), (0, 1)), "h": (Fraction(3600), (0, 1)),
    "mm": (Fraction(1, 1000), (1, 0)), "cm": (Fraction(1, 100), (1, 0)),
    "m": (Fraction(1), (1, 0)), "km": (Fraction(1000), (1, 0)),
    "one": (Fraction(1), (0, 0)),
})


def literal(token, unit, meter, file):
    def check(value):
        meter.check("integer_bits", abs(value).bit_length(), file=file, span=token.span)
        return value
    whole, _, decimal = token.lexeme.partition(".")
    numerator = check(int(whole + decimal))
    bits = int(len(decimal) * log2(10)) + 1
    meter.check("integer_bits", bits, file=file, span=token.span)
    denominator = 10 ** len(decimal)
    scale, dimensions = UNITS[unit]
    a, b = gcd(numerator, scale.denominator), gcd(denominator, scale.numerator)
    # Literal text is already bounded; check exact product width before allocation.
    for left, right in ((numerator // a, scale.numerator // b),
                        (denominator // b, scale.denominator // a)):
        if left and right:
            width = left.bit_length() + right.bit_length()
            if width > meter.policy.limits["integer_bits"]:
                # Comparing with the largest allowed factor avoids false rejection
                # at the one-bit uncertainty of a product-width upper bound.
                limit = meter.policy.limits["integer_bits"]
                meter.check("integer_bits", limit + (left > ((1 << limit) - 1) // right),
                            file=file, span=token.span)
    value = Fraction(check((numerator // a) * (scale.numerator // b)),
                     check((denominator // b) * (scale.denominator // a)))
    for exponent in dimensions:
        meter.check("quantity_exponent_abs", abs(exponent), file=file, span=token.span)
    return value, dimensions


def value(runtime, number, dimensions, node):
    integers = (number.numerator, number.denominator, *dimensions)
    for integer in integers[:2]:
        runtime.check("integer_bits", abs(integer).bit_length(), node)
    for exponent in dimensions:
        runtime.check("quantity_exponent_abs", abs(exponent), node)
    size = sum((abs(n).bit_length() + 7) // 8 for n in integers)
    return Value("Quantity", (number, dimensions), runtime.reserve(node, runtime_payload_bytes=size))


def calculate(runtime, operation, left, right, node):
    a, ad = left.data if left.kind == "Quantity" else (Fraction(left.data), (0, 0))
    b, bd = right.data if right.kind == "Quantity" else (Fraction(right.data), (0, 0))
    owners = []
    def integer(op, x, y):
        result = runtime.integer_operation(op, x, y, node)
        owners.append(result)
        return result.data
    # Fraction(float) preserves the actual binary value, including its denominator.
    for number in (a, b):
        runtime.check("integer_bits", abs(number.numerator).bit_length(), node)
        runtime.check("integer_bits", number.denominator.bit_length(), node)
    if operation in {"LESS", "LESS_EQUAL", "GREATER", "GREATER_EQUAL", "PLUS", "MINUS"}:
        if left.kind != right.kind or ad != bd:
            runtime.error(node, "E213" if left.kind == right.kind else "E201", "数量量纲不匹配")
    with runtime.reserve(node, runtime_payload_bytes=sum((abs(x).bit_length()+7)//8
            for x in (a.numerator, a.denominator, b.numerator, b.denominator))):
        if operation in {"MULTIPLY", "DIVIDE"}:
            if operation == "DIVIDE":
                if not b:
                    runtime.error(node, "E205", "除数不能为零")
                b = 1 / b
            dimensions = tuple(x + (y if operation == "MULTIPLY" else -y) for x, y in zip(ad, bd))
            for exponent in dimensions:
                runtime.check("quantity_exponent_abs", abs(exponent), node)
            g, h = gcd(a.numerator, b.denominator), gcd(b.numerator, a.denominator)
            numerator = integer("MULTIPLY", a.numerator//g, b.numerator//h)
            denominator = integer("MULTIPLY", a.denominator//h, b.denominator//g)
        else:
            g = gcd(a.denominator, b.denominator)
            x = integer("MULTIPLY", a.numerator, b.denominator//g)
            y = integer("MULTIPLY", b.numerator, a.denominator//g)
            if operation in {"LESS", "LESS_EQUAL", "GREATER", "GREATER_EQUAL"}:
                return boolean({"LESS": x < y, "LESS_EQUAL": x <= y,
                                "GREATER": x > y, "GREATER_EQUAL": x >= y}[operation])
            numerator = integer(operation, x, y)
            denominator = integer("MULTIPLY", a.denominator, b.denominator//g)
            dimensions = ad
        return value(runtime, Fraction(numerator, denominator), dimensions, node)


def text(runtime, quantity, node):
    number, dimensions = quantity.data
    numerator = runtime.text_value(Value("Int", number.numerator), node)
    denominator = runtime.text_value(Value("Int", number.denominator), node) if number.denominator != 1 else None
    labels = [name if power == 1 else f"{name}^{power}" for name, power in zip(("m", "s"), dimensions) if power]
    return join_text(runtime, (numerator.data, "/" if denominator else "", denominator.data if denominator else "",
                               "::", "*".join(labels) or "one"), node)


def join_text(runtime, parts, node):
    size = sum(map(len, parts))
    runtime.check("text_codepoints", size, node)
    owner = runtime.reserve(node, runtime_payload_bytes=4 * size)
    return Value("String", "".join(parts), owner)
