def gen_func():
    yield 1
    yield 2
    yield 3
    return 'bobby'

if __name__ == '__main__':
    g = gen_func()
    print(next(g))
    print(next(g))
    print(next(g))
    print(next(g))
