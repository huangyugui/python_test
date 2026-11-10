import abc


class Company(object):
    def __init__(self, employees):
        self.employees = employees

    def __len__(self):
        return len(self.employees)


from abc import ABCMeta
class Cache(metaclass=ABCMeta):

    @abc.abstractmethod
    def get(self):
        pass

    @abc.abstractmethod
    def set(self, key, value):
        pass

class RedisCache(Cache):
    def get(self):
        pass

    def set(self, key, value):
        pass

class Cache1:
    def get(self):
        raise NotImplementedError
    def set(self, key, value):
        raise NotImplementedError

class RedisCache1(Cache1):
    pass

if __name__ == '__main__':
    # 希望判定某个对象的类型
    com = Company([1, 2, 3])
    from _collections_abc import Sized
    print(isinstance(com, Sized))

    # 需要设计一个抽象类，指定子类必须实现某些方法
    # 1、如果没有实现指定的方法，在初始化时就会报错
    rcache = RedisCache()
    print(isinstance(rcache, RedisCache))

    # 2、如果采用Cache1的方式，在调用时才会报错
    rcache1 = RedisCache1()
    print(isinstance(rcache1, RedisCache1))

    # 尽量使用isinstance，而非type
    print(isinstance(rcache1, RedisCache1))
    print(isinstance(rcache1, Cache1))
    print(type(rcache1) is RedisCache1)   # True
    print(type(rcache1) is Cache1)      # False

    # 这里要注意is 和 ==是不能随便混用的
    # 1、is代表的是身份(id())是否一致,是否指向的是内存中的同一块内存地址；而==标识值是否相等
    print(id(type(rcache1)))
    print(id(RedisCache1))
