class Container:
    def __init__(self, name, employees):
        self.name = name
        self.employees = employees

    def __len__(self):
        return len(self.employees)

    def __iter__(self):
        return iter(self.employees)

    def __getitem__(self, key):
        return self.employees[key]

    def __setitem__(self, key, value):
        self.employees[key] = value

    def __delitem__(self, key):
        del self.employees[key]

    # def __contains__(self, key):
    #     return key in self.employees

    def __str__(self):
        return ", ".join(self.employees)



if __name__ == '__main__':
    myContainer = Container("myContainer", ["1", "2", "3"])
    print(myContainer)
    print(len(myContainer))
    print(myContainer[1])
    myContainer[2] = "4"
    print(myContainer)
    del myContainer[1]
    print(myContainer)
    myContainer.employees.append("5")
    print(myContainer)
    print("1" in myContainer)
