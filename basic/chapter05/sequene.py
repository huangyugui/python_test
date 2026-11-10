from collections import abc


print("tuple 有 __add__ 吗:", hasattr(tuple, "__add__"), "| 有 __iadd__ 吗:", hasattr(tuple, "__iadd__"))
print("int   有 __add__ 吗:", hasattr(int, "__add__"), "| 有 __iadd__ 吗:", hasattr(int, "__iadd__"))
print("str   有 __add__ 吗:", hasattr(str, "__add__"), "| 有 __iadd__ 吗:", hasattr(str, "__iadd__"))
print("list  有 __add__ 吗:", hasattr(list, "__add__"), "| 有 __iadd__ 吗:", hasattr(list, "__iadd__"))

print("--------" * 20)
# += 看是否退化为__add__，如果退化的话，则生成新对象，因为__add__不会动原对象
# list 可变：+= 原地
a = [1, 2]
id_before = id(a)
a += [3]
print("list 原地:", id(a) == id_before, a)      # True [1, 2, 3]

# tuple 不可变：+= 回退到 __add__，重新绑定
t = (1, 2)
id_before = id(t)
t += (3,)
print("tuple 新对象:", id(t) == id_before, t)   # False (1, 2, 3)

# list 可变：+ 重新绑定
a = [1, 2]
id_before = id(a)
a = a + [3]
print("list 新对象:", id(a) == id_before, a)      # False [1, 2, 3]

# tuple 不可变：+，重新绑定
t = (1, 2)
id_before = id(t)
t += (3,)
print("tuple 新对象:", id(t) == id_before, t)   # False (1, 2, 3)

print("-" * 20)

# 自定义类：同时定义 __add__ 和 __iadd__
class Bag:
    def __init__(self, items=None):
        self.items = list(items or [])
    def __add__(self, other):
        print("→ __add__（返回新对象）")
        return Bag(self.items + other.items)
    def __iadd__(self, other):
        print("→ __iadd__（原地修改并返回 self）")
        self.items.extend(other.items)
        return self

b = Bag([1])
b += Bag([2])
print("Bag items:", b.items)                    # [1, 2]

# 只定义 __add__：+= 自动回退
class NoIadd:
    def __init__(self, items=None):
        self.items = list(items or [])
    def __add__(self, other):
        print("→ 只有 __add__，+= 回退（返回新对象）")
        return NoIadd(self.items + other.items)

n = NoIadd([1])
n += NoIadd([2])
print("NoIadd items:", n.items)                 # [1, 2]




print("-" * 20)
a = [1, 2, 3]
id_before= id(a)
a *= 2
print("是否新对象", id(a) == id_before, a)