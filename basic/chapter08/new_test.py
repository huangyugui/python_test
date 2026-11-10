class User:
    def __new__(cls, *args, **kwargs):
        print(f'args: {args}, kwargs: {kwargs}')
        # 必须要返回实例对象才能进行后面的__init__
        return super().__new__(cls)

    def __init__(self, name, age):
        self._name = name
        self._age = age


if __name__ == '__main__':
    user = User("zhangsan", 10)
    print(user.__dict__)
    user1 = User(name="lisi", age=20)
    print(user1.__dict__)