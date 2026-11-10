import threading, dis

lock = threading.Lock
counter = 0

def nop():
    # 空函数调用，函数调用入口是安全点！
    pass

def increment():
    global counter
    for _ in range(1000000):
        # 拆开来写，把读和写分开，中间插入函数调用（安全点）
        tmp = counter
        nop()  # 这里是安全点！GIL 很大概率在这里切换
        counter = tmp + 1

if __name__ == '__main__':
    t1 = threading.Thread(target=increment)
    t2 = threading.Thread(target=increment)
    t1.start(); t2.start()
    t1.join(); t2.join()
    print(counter)

    # dis.dis(increment)