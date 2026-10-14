from benchmarks.reference import CheckedArray

n = 97
numbers = []
for i in range(n):
    numbers.append(i)
checked = CheckedArray(numbers)


def bench():
    return checked.sum()


if __name__ == '__main__':
    print(bench())
