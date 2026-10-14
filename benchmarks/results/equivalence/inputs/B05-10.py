from benchmarks.reference import CheckedArray

n = 10
numbers = []
for i in range(n):
    numbers.append((n - 1 - i) % 97)
checked = CheckedArray(numbers)


def bench():
    return checked.sorted()


if __name__ == '__main__':
    print(bench())
    print(numbers)
