n = 1


def inc(x):
    return x + 1


def bench():
    i = total = 0
    while i < n:
        total = total + inc(i)
        i = i + 1
    return total


if __name__ == '__main__':
    print(bench())
