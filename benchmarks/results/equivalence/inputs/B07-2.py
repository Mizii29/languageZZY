from benchmarks.reference import query

n = 2
tasks = []
for i in range(n):
    tasks.append({'id': i, 'done': i % 3 == 0, 'priority': i % 5})


def bench():
    return query(tasks)


if __name__ == '__main__':
    print(bench())
