n = 0
def term(i):
    if i % 2 == 0:
        return i + 1
    return i - 1


def bench():
    i = total = 0
    while i < n:
        total = total + term(i)
        i = i + 1
    return total


if __name__ == '__main__':
    print(bench())
