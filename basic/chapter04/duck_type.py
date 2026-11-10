# 鸭子类型，不同的类只要实现了相同的方法，那么就可以实现java中接口的效果
class Dog:
    def say(self):
        print("I am dog.")

class Cat:
    def say(self):
        print("I am cat.")

class Duck:
    def say(self):
        print("I am duck.")

animal_list = [Dog(), Cat(), Duck()]
for animal in animal_list:
    animal.say()

# 魔法函数就是利用了鸭子类型, list 和 set 都是可迭代对象，因此extend时，接收的是一个可迭代对象，此时list可以extend set
list = [1, 2, 3]
set = {4, 5, 6}
list.extend(set)

print(list)

from basic.chapter03.container import Container

container = Container("container", [7, 8, 9])

list.extend(container)
print(list)