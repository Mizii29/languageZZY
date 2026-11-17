"""Independent CPython implementations matching the experiment's loops."""


def sum_squares(n):
    i = 0
    total = 0
    while i < n:
        total = total + i * i
        i = i + 1
    return total


def branch_calls(n):
    def term(i):
        if i % 2 == 0:
            return i + 1
        return i - 1

    i = 0
    total = 0
    while i < n:
        total = total + term(i)
        i = i + 1
    return total
