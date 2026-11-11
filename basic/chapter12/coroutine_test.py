def gen_func():
    yield 1
    yield 2
    yield 3
    # return的值会随着StopIteration抛出去，可以通过value来获取值
    return 'bobby'

def gen_func2():
    #可以通过send的方式来将值传递进来
    value = yield 1
    print(value)
    yield 2

def gen_func3():
    try:
        yield 1
    except ValueError as e:
        # 到这里会抛出StopIteration，因为后面没有yield了
        return "abc"

def gen_func4():
    yield 1
    yield 2

def gen_func5():
    yield 1
    # 协程中抛出异常，会一直向上抛的
    raise ValueError("abc")
    yield 2

if __name__ == '__main__':
    g = gen_func5()
    g.send(None)
    try:
        g.send(None)
    except ValueError as e:
        print(e)


    # g = gen_func4()
    # g.send(None)
    # g.close()


    # g = gen_func3()
    # print(next(g))
    # # print(g.throw(ValueError("abc")))
    # try:
    #     g.throw(ValueError("ddb"))
    # except StopIteration as e:
    #     print(e.value)

    # g = gen_func2()
    # print(next(g)) # 预激一下，也可以使用g.send(None)
    # print(g.send("你好"))
    # try:
    #     print(next(g))
    # except StopIteration as e:
    #     #如果没有return，则value为None
    #     print(e.value)


    # g = gen_func()
    # print(next(g))
    # print(next(g))
    # print(next(g))
    # try:
    #     print(next(g))
    # except StopIteration as e:
    #     print(e.value)
