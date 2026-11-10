from datetime import date

class User:
    def __init__(self, name, birthday):
        self._name = name
        self._birthday = birthday

    @property
    def name(self):
        return self._name

    @property
    def birthday(self):
        return self._birthday

    @property
    def age(self):
        return date.today().year - self.birthday.year

    # @age.setter
    # def age(self, value):
    #     self._age = value
    #
    # @age.deleter
    # def age(self):
    #     del self._age


if __name__ == '__main__':
    user = User("zhangsan", date(1999, 10, 31))
    print(user.age)
    # user.age = 20
    print(user.age)
    print(user.__dict__)

    # del user.age
    # print(user._age)

