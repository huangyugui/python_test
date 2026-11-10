class D:
    pass
class B(D):
    pass
class C(D):
    pass
class A(B, C):
    pass

class D1:
    pass
class E1:
    pass
class B1(D1):
    pass
class C1(E1):
    pass
class A1(B1, C1):
    pass

if __name__ == '__main__':
    # python3 之后统一采用C3算法
    print(A.__mro__) # (<class '__main__.A'>, <class '__main__.B'>, <class '__main__.C'>, <class '__main__.D'>, <class 'object'>)
    print(A1.__mro__) # (<class '__main__.A1'>, <class '__main__.B1'>, <class '__main__.D1'>, <class '__main__.C1'>, <class '__main__.E1'>, <class 'object'>)