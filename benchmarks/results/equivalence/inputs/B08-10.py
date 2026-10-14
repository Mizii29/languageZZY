from benchmarks.reference import Machine

n = 10
graph = {('a', 'flip'): 'b', ('b', 'flip'): 'a'}
machine = Machine(graph, 'a')


def bench():
    i = successes = 0
    while i < n:
        ok, state = machine.send('flip')
        if ok:
            successes = successes + 1
        else:
            raise AssertionError(state)
        i = i + 1
    return [successes, machine.state]


if __name__ == '__main__':
    result = bench()
    print(f'[{result[0]}, {result[1]}]')
