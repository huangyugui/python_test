from collections.abc import Iterable, Iterator


class Company:
    def __init__(self, employees):
        self.employees = employees

    def __iter__(self):
        # 返回一个迭代器
        # return iter(self.employees)
        return MyIterator(self.employees)

class MyIterator(Iterator):
    def __init__(self, list):
        self.list = list
        self.index = 0

    # 继承了Iterator，也可以不实现__iter__
    def __iter__(self):
        return self

    # 当抛出StopIteration时，表示到头了，for就是根据这个来停止遍历的 
    def __next__(self):
        try:
            value = self.list[self.index]
            self.index += 1
            return value
        except IndexError:
            raise StopIteration

if __name__ == '__main__':
    print(isinstance([1, 2], Iterable))   # True
    print(isinstance([1, 2], Iterator))   # False
    # list 是有一个可迭代对象，调用iter()返回迭代器
    print(isinstance(iter([1, 2]), Iterator))  # True
    print("-" * 60)

    com = Company(["tom", "jone", 'lily'])
    for employee in com:
        print(employee)