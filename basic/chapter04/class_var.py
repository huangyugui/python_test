class A:
    aa = 1

    def __init__(self, a):
        self.a = a

if __name__ == '__main__':
    a = A(2)
    # 如果a实例的属性中没有aa属性，则去取类上的属性的值
    print(A.aa)
    print(a.aa)

    # 如果对实例进行赋值，此时会在实例上新增一个属性，而不是修改类的属性，这点与java不同
    a.aa = 10
    print(a.aa)
    print(A.aa)
