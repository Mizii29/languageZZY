n = 1000


def bench():
    i = total = 0
    while i < n:
        total = total + i
        i = i + 1
    return total


if __name__ == '__main__':
    print(bench())
