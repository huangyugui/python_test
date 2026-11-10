def gen_fib(n):
    index, a, b = 0, 0, 1
    while index < n:
        yield b
        a, b = b, a+b
        index += 1

if __name__ == '__main__':
    for n in gen_fib(10):
        print(n)