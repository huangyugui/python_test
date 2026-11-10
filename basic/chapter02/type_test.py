print(type(1))
print(type("str"))
print(type((1, 2, 3)))
print(type([1, 2, 3]))
print(type({1: 2, 2: 4}))

class Student:
    pass

class MyStudent(Student):
    pass

# 类的类型是type
# type -> class -> obj
print(type(Student))
# 实例的type是具体的类
print(type(Student()))
print(type(MyStudent()))

# type 的类型也是type
print(type(type(Student)))

print(isinstance(MyStudent(), Student))

# type(x) —— 精确类型
# 返回类型对象，等价 x.__class__
# 不做继承判断：子类实例一律不命中基类
# 适合"必须精确类型"：如用 type(x) is int 排除 bool
# 不支持多类型元组，需自行写 in (T1, T2)
# 不认识 ABC 虚子类（__instancecheck__ 不生效）
# `type(x)` 与 `x.__class__` 通常等价，但 `type` 走的是类型系统内部，更可靠。

# isinstance(x, T) —— 继承链检查
# 沿 MRO 向上遍历，子类实例也命中
# 原生支持元组：(int, float)
# 支持 ABC 虚子类：Iterable、Number 等
# bool 是 int 子类：isinstance(True, int) 为 True
# 第二个参数必须是类型或类型元组，传实例会 TypeError

# 句话收尾：**`type` 问的是 "你具体是哪个类"，`isinstance` 问的是 "你算不算这一类（含它的所有子类）"**。

print("-" * 20)
# 一切皆对象
print(MyStudent.__bases__)
print(type.__bases__)
# Object的基类是空
print(object.__bases__)

print("-" * 20)

