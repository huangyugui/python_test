class JSONMixin:
    def to_json(self):
        import json
        return json.dumps(self.__dict__)

class Animal:
    def __init__(self, name):
        self._name = name
        self.__age = 3

    @classmethod
    def create(cls, name, age):
        obj = cls(name)
        obj.__age = age
        return obj

    def speak(self):
        return "..."

class Dog(JSONMixin, Animal):
    def speak(self):
        return "Woof"

d = Dog.create("旺财", 5)
print(d.__dict__)
print(d.__age)

