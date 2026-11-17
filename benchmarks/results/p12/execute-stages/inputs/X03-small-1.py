n = 1


def bench():
    numbers = []
    i = 0
    while i < n:
        numbers.append(i)
        i = i + 1
    total = 0
    for number in numbers:
        total = total + number
    return [len(numbers), total]


if __name__ == '__main__':
    print(bench())
