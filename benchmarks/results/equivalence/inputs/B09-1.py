from fractions import Fraction
from benchmarks.reference import quantity_add, quantity_text

n = 1
zero = (Fraction(0), (0, 1))
step = (Fraction(1, 1000), (0, 1))


def bench():
    total = zero
    i = 0
    while i < n:
        total = quantity_add(total, step)
        i = i + 1
    return total


if __name__ == '__main__':
    print(quantity_text(bench()))
