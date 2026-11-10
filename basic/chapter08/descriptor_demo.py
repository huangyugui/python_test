# -*- coding: utf-8 -*-
"""描述符查找优先级验证：
数据描述符 > 实例 __dict__ > 非数据描述符 > 普通类属性 > __getattr__ > AttributeError
"""

print("=" * 60)
print("演示1：数据描述符优先于实例 __dict__（读和写都拦截）")
print("=" * 60)

class DataDesc:
    def __get__(self, obj, objtype=None):
        print("  [DataDesc.__get__ 被调用]")
        return "来自数据描述符"

    def __set__(self, obj, value):
        print(f"  [DataDesc.__set__ 被调用] value={value!r}")
        obj.__dict__['d'] = value  # 故意写进实例字典做对比

class A:
    d = DataDesc()

a = A()
a.d = 10          # 写：被 __set__ 拦截
print("  实例字典:", a.__dict__)
print("  a.d =", a.d)   # 读：实例字典里明明有 'd'，仍然走 __get__


print()
print("=" * 60)
print("演示2：实例 __dict__ 优先于非数据描述符")
print("=" * 60)

class NonDataDesc:
    def __get__(self, obj, objtype=None):
        print("  [NonDataDesc.__get__ 被调用]")
        return "来自非数据描述符"

class B:
    d = NonDataDesc()

b = B()
print("  第一次 b.d =", b.d)              # 走 __get__
b.__dict__['d'] = "实例字典的值"          # 往实例字典塞同名属性
print("  第二次 b.d =", b.d)              # __get__ 不再被调用！


print()
print("=" * 60)
print("演示3：property 是数据描述符，无法被实例字典绕过")
print("=" * 60)

class C:
    @property
    def x(self):
        return "property 的值"

c = C()
c.__dict__['x'] = "试图绕过 property"
print("  c.x =", c.x)   # 依然是 property 的值


print()
print("=" * 60)
print("演示4：函数是非数据描述符 —— self 绑定的秘密")
print("=" * 60)

class D:
    def hello(self):
        return "hello"

d = D()
print("  D.hello   :", D.hello)   # 类访问：__get__(None, D) 返回普通函数
print("  d.hello   :", d.hello)   # 实例访问：__get__(d, D) 返回绑定方法
d.__dict__['hello'] = lambda: "实例属性遮蔽了方法"
print("  遮蔽后    :", d.hello()) # 非数据描述符可被实例字典遮蔽


print()
print("=" * 60)
print("演示5：cached_property —— 非数据描述符实现缓存的经典")
print("=" * 60)

import functools

class Report:
    @functools.cached_property
    def total(self):
        print("  [昂贵的计算，只应执行一次]")
        return sum(range(1_000_000))

r = Report()
print("  第一次 r.total =", r.total)
print("  第二次 r.total =", r.total)          # 不再打印"昂贵的计算"
print("  缓存落点: 'total' in r.__dict__ ->", 'total' in r.__dict__)


print()
print("=" * 60)
print("演示6：__getattr__ 是最后兜底")
print("=" * 60)

class E:
    def __getattr__(self, name):
        print(f"  [__getattr__ 兜底] name={name!r}")
        return f"<兜底值 {name}>"

print("  e.nothing =", E().nothing)

class F:
    pass
try:
    F().nothing
except AttributeError as ex:
    print("  没有 __getattr__ 时:", type(ex).__name__)


print()
print("=" * 60)
print("演示7：实战 —— ORM 风格的校验字段(数据) + 惰性加载(非数据)")
print("=" * 60)

class IntegerField:
    """数据描述符：赋值时校验，读取时取值（存储委托给实例字典）"""
    def __set_name__(self, owner, name):    # 类创建时自动调用，拿到属性名
        self.name = name

    def __repr__(self):
        return f"<IntegerField {self.name!r}>"

    def __get__(self, obj, objtype=None):
        if obj is None:                      # 通过类访问 Order.qty 返回描述符本身
            return self
        return obj.__dict__.get(self.name)

    def __set__(self, obj, value):
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"{self.name} 必须是非负整数，收到 {value!r}")
        obj.__dict__[self.name] = value

def make_conn():
    print("  [执行昂贵的连接创建]")
    return "<假数据库连接>"

class LazyConn:
    """非数据描述符：首次访问时计算并写回实例字典，之后查找在步骤(2)直接命中"""
    def __init__(self, factory):
        self.factory = factory

    def __set_name__(self, owner, name):
        self.attr = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        value = self.factory()
        obj.__dict__[self.attr] = value      # 写回实例字典 -> 之后不再走 __get__
        return value

class Order:
    qty = IntegerField()
    db = LazyConn(make_conn)

o = Order()
o.qty = 5
print("  o.qty =", o.qty)
try:
    o.qty = -1
except ValueError as ex:
    print("  校验生效:", ex)
print("  第一次 o.db =", o.db)   # 执行 factory
print("  第二次 o.db =", o.db)   # factory 不再执行
print("  Order.qty =", Order.qty)
