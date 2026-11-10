import abc


def make_sound(animal):
    print(animal.speak())

class Dog:
    def speak(self):
        return "wangwangwang"

class Duck:
    def speak(self):
        return "gagaga"

class Cat:
    def speak(self):
        return "miaomiaomiao"


class Animal1:
    def speak(self):
        pass

    def say(self):
        print("say a word~")

class Dog1(Animal1):
    def speak(self):
        #调用父类的方法
        super().say()
        return "wangwangwang"

class Duck1(Animal1):
    def speak(self):
        return "gagaga"


from abc import ABCMeta
class Animal2(metaclass=ABCMeta):
    @abc.abstractmethod
    def speak(self):
        ...

class Dog2(Animal2):
    def speak(self):
        return "wangwangwang"


if __name__ == '__main__':
    make_sound(Dog())

    animal1 = Dog1()
    print(animal1.speak())

    animal2 = Dog2()
    print(animal2.speak())