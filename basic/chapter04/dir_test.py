class Animal1:
    def speak(self):
        pass

    def say(self):
        print("say a word~")

class Dog1(Animal1):
    def __init__(self, name):
        self.name = name


    def speak(self):
        """
        说话
        """
        #调用父类的方法
        super().say()
        return "wangwangwang"

class Duck1(Animal1):
    def speak(self):
        return "gagaga"


if __name__ == '__main__':
    d = Dog1("小白")
    print(d.__dict__)

    print(Dog1.__dict__)
    print(Dog1.__module__)
    print(Dog1.__doc__)
    print(Dog1.speak.__doc__)

    print("-" * 20)
    print(dir(Dog1))

