class A:
    def __init__(self):
        print("A")

class B(A):
    def __init__(self):
        print("B")
        super().__init__()

class C(A):
    def __init__(self):
        print("C")
        super().__init__()

class D(B, C):
    def __init__(self):
        print("D")
        super().__init__()

if __name__ == '__main__':
    # 调用super时，是按照mro的顺序来调用的
    print(D.__mro__)
    d = D()