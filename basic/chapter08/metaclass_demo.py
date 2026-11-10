# -*- coding: utf-8 -*-
"""元类文档配套验证脚本（跑完即删）"""


def case1_类是对象():
    class Foo:
        pass

    print(type(Foo))            # <class 'type'>
    print(type(type) is type)   # True，type 是自己的元类
    print(isinstance(Foo, type))  # True


def case2_type动态建类():
    def bark(self):
        return "汪"

    Dog = type("Dog", (object,), {"legs": 4, "bark": bark})
    d = Dog()
    print(d.legs, d.bark())     # 4 汪
    print(type(d))              # <class '__main__.Dog'>


def case3_元类三钩子():
    log = []

    class Meta(type):
        def __new__(mcls, name, bases, ns, extra=None, **kwargs):
            # extra 必须由元类自己吃掉，否则会被 type.__new__ 转发给
            # 父类的 __init_subclass__，而 object.__init_subclass__ 不收额外参数
            log.append(f"Meta.__new__: 造类 {name}, extra={extra}")
            return super().__new__(mcls, name, bases, ns, **kwargs)

        def __init__(cls, name, bases, ns, **kwargs):
            log.append(f"Meta.__init__: 初始化类 {name}")
            super().__init__(name, bases, ns, **kwargs)

        def __call__(cls, *args, **kwargs):
            log.append(f"Meta.__call__: {cls.__name__}(...) 实例化")
            return super().__call__(*args, **kwargs)

    class Person(metaclass=Meta, extra=1):
        def __init__(self, name):
            self.name = name

    p = Person("Tom")
    print(p.name)
    for line in log:
        print(line)


def case4_插件注册():
    PLUGINS = {}

    class PluginMeta(type):
        def __new__(mcls, name, bases, ns):
            cls = super().__new__(mcls, name, bases, ns)
            if bases:  # 跳过基类自身
                PLUGINS[ns.get("name", name)] = cls
            return cls

    class Plugin(metaclass=PluginMeta):
        pass

    class ZipPlugin(Plugin):
        name = "zip"

    class GzipPlugin(Plugin):
        pass  # 没写 name，用类名兜底

    print(sorted(PLUGINS))  # ['GzipPlugin', 'zip']


def case5_ORM字段收集():
    class Field:
        def __init__(self, dtype, required=False):
            self.dtype = dtype
            self.required = required
            self.storage_name = None  # 由元类设置

        def __set__(self, obj, value):
            if not isinstance(value, self.dtype):
                raise TypeError(f"{self.storage_name} 需要 {self.dtype.__name__}")
            obj.__dict__[self.storage_name] = value

        def __get__(self, obj, owner):
            if obj is None:
                return self
            return obj.__dict__.get(self.storage_name)

    class ModelMeta(type):
        def __new__(mcls, name, bases, ns):
            fields = {}
            for base in bases:  # 继承父类字段
                fields.update(getattr(base, "_fields", {}))
            for key, val in list(ns.items()):
                if isinstance(val, Field):
                    val.storage_name = key
                    fields[key] = val
            cls = super().__new__(mcls, name, bases, ns)
            cls._fields = fields
            return cls

    class Model(metaclass=ModelMeta):
        def __init__(self, **kwargs):
            missing = [f for f, spec in self._fields.items()
                       if spec.required and f not in kwargs]
            if missing:
                raise TypeError(f"缺少必填字段: {missing}")
            for k, v in kwargs.items():
                setattr(self, k, v)

        def to_dict(self):
            return {k: getattr(self, k) for k in self._fields}

    class User(Model):
        name = Field(str, required=True)
        age = Field(int)

    u = User(name="Tom", age=18)
    print(u.to_dict())          # {'name': 'Tom', 'age': 18}
    try:
        User(name=123)
    except TypeError as e:
        print("拦截成功:", e)    # name 需要 str
    try:
        User(age=1)
    except TypeError as e:
        print("拦截成功:", e)    # 缺少必填字段 ['name']
    print(User._fields)         # 字段收集结果


def case6_元类单例():
    class SingletonMeta(type):
        _instances = {}

        def __call__(cls, *args, **kwargs):
            if cls not in cls._instances:
                cls._instances[cls] = super().__call__(*args, **kwargs)
            return cls._instances[cls]

    class Config(metaclass=SingletonMeta):
        pass

    class Logger(metaclass=SingletonMeta):
        pass

    a, b = Config(), Config()
    print(a is b)               # True
    print(Config() is Logger()) # False，不同类各自单例


def case7_接口强制检查():
    class APIMeta(type):
        REQUIRED = ("run", "name")

        def __new__(mcls, name, bases, ns):
            if bases:  # 排除 API 自身
                for member in APIMeta.REQUIRED:
                    inherited = any(member in b.__dict__ or
                                    hasattr(b, member) for b in bases)
                    if member not in ns and not inherited:
                        raise TypeError(f"{name} 缺少必需成员: {member}")
            return super().__new__(mcls, name, bases, ns)

    class API(metaclass=APIMeta):
        pass

    class GoodAPI(API):
        name = "good"
        def run(self):
            return "ok"

    print(GoodAPI().run())
    try:
        class BadAPI(API):
            name = "bad"
    except TypeError as e:
        print("拦截成功:", e)    # BadAPI 缺少必需成员: run


def case8_metaclass冲突():
    class MetaA(type):
        pass

    class MetaB(type):
        pass

    class A(metaclass=MetaA):
        pass

    class B(metaclass=MetaB):
        pass

    try:
        class C(A, B):
            pass
    except TypeError as e:
        print("冲突拦截:", e)


def case9_init_subclass替代():
    PLUGINS = {}

    class Plugin:
        def __init_subclass__(cls, *, plugin_name=None, **kwargs):
            super().__init_subclass__(**kwargs)
            PLUGINS[plugin_name or cls.__name__] = cls

    class ZipPlugin(Plugin, plugin_name="zip"):
        pass

    class GzipPlugin(Plugin):
        pass

    print(sorted(PLUGINS))  # ['GzipPlugin', 'zip']


def case10_prepare():
    class OrderedMeta(type):
        @classmethod
        def __prepare__(mcls, name, bases, **kwargs):
            print("__prepare__: 提供命名空间（类体执行之前）")
            return {}

        def __new__(mcls, name, bases, ns, **kwargs):
            print("__new__: 类体执行完，ns =", list(ns))
            return super().__new__(mcls, name, bases, ns, **kwargs)

    class Foo(metaclass=OrderedMeta):
        x = 1

    print(Foo.x)


if __name__ == "__main__":
    import sys
    print("=== Python", sys.version.split()[0], "===")
    for fn in [case1_类是对象, case2_type动态建类, case3_元类三钩子,
               case4_插件注册, case5_ORM字段收集, case6_元类单例,
               case7_接口强制检查, case8_metaclass冲突,
               case9_init_subclass替代, case10_prepare]:
        print(f"\n--- {fn.__name__} ---")
        fn()
