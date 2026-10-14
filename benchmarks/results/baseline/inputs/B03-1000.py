n = 1000
numbers = []
for i in range(n):
    numbers.append(i)


def bench():
    total = 0
    for number in numbers:
        total = total + number
    return total


if __name__ == '__main__':
    print(bench())
