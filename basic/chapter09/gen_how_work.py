import dis

def gen_func():
    yield 1
    name = "zhangsan"
    yield 2
    age = 10
    return "tiantianxiangshan"

if __name__ == '__main__':
    gen = gen_func()
    print(dis.dis(gen))

    print("-" * 60)
    print(gen.gi_frame.f_lasti)
    print(gen.gi_frame.f_locals)
    next(gen)
    print(gen.gi_frame.f_lasti)
    print(gen.gi_frame.f_locals)
    next(gen)
    print(gen.gi_frame.f_lasti)
    print(gen.gi_frame.f_locals)
