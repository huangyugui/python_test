# Python 元类详解与元类编程（metaclass）

> 存放位置：`basic\chapter08\md\Python元类详解与元类编程.md`
> 前置知识：`__init__` 与 `__new__` 的区别（见同章）、描述符协议（见同章）、type 与 isinstance（chapter02）、MRO 与继承（chapter04）
> 配套代码：`basic\chapter08\metaclass_demo.py`（本文所有代码与结论均在 `D:\python\fastapi_test\.venv`，Python 3.13.9 实测通过）

## 一句话结论

**元类 = "造类"的类**。你写 `class Foo:` 时，Python 拿着类名、基类、类体字典三样东西，调用一个"幕后工厂"把 `Foo` 这个类对象造出来——这个工厂默认是 `type`，换成你自己的类（必须继承 `type`）就是**自定义元类**。于是："类是元类的实例"，实例生命周期的 `__new__`/`__init__`/`__call__` 那套规则，原封不动地搬到了类这一层。

---

## 1. 先建立直觉：类也是对象，那谁来"造"类？

Python 里一切皆对象，`class Foo:` 写完后，`Foo` 本身就是个对象。既然是对象，它就该有自己的类型：

```python
class Foo:
    pass

print(type(Foo))             # <class 'type'>  ← 类的类型是 type
print(type(type) is type)    # True            ← type 是自己的元类，链条到此为止
print(isinstance(Foo, type)) # True            ← Foo 是 type 的实例
```

三层关系一句话：

| 对象 | 它的类型 | 谁造它 |
|---|---|---|
| `d = Dog()` | `Dog`（类） | `Dog.__new__` / `Dog.__init__` |
| `Dog`（类） | `type`（元类） | `type.__new__` / `type.__init__` |
| `type` | `type`（自己） | — |

**实例由类创建，类由元类创建**。`__init__与__new__的区别.md` 里讲的那套"先 `__new__` 造对象、再 `__init__` 初始化、`MyClass(x)` 走 `type(MyClass).__call__`"的规则，把"实例"换成"类"之后依然成立——这就是元类全部原理的底座。

## 2. `type()` 三参调用：手动造一个类

`type` 有两张面孔：一个参数时是"查类型"的函数，三个参数时就是造类的工厂：

```python
type(名字, 基类元组, 属性字典)
```

```python
def bark(self):
    return "汪"

Dog = type("Dog", (object,), {"legs": 4, "bark": bark})

d = Dog()
print(d.legs, d.bark())   # 4 汪
print(type(d))            # <class '__main__.Dog'>  和 class 语句写的没差别
```

三个要素对应 `class` 语句的三个部分：

| type() 参数 | 对应 class 语句 | 说明 |
|---|---|---|
| `name` | 类名 `class Dog` | 字符串 |
| `bases` | 括号里的基类 `(Base,)` | 元组，可为空（默认补 `object`） |
| `ns` | 类体执行后的命名空间 | 字典：方法、类属性、`__module__` 等全在里面 |

所以 **`class` 语句本质是 `type(...)` 的语法糖**：先执行类体攒出一个字典，再交给元类造类。既然造类的工序可以被替换，就有了元类编程的空间。

## 3. `class` 语句的完整幕后流程（元类在哪里介入）

写 `class Person(Base, metaclass=Meta, extra=1):` 时，解释器按这个顺序干活：

```
① 确定元类：显式 metaclass=Meta 优先；否则取所有基类元类中最派生的；再否则 type
② meta.__prepare__(name, bases, ...)  → 返回命名空间容器（默认空 dict）
③ 执行类体，逐条填进 ② 返回的容器
④ 调用 meta(name, bases, ns, extra=1)
      └─ type.__call__ 接住 → Meta.__new__(...)  造出类对象
                           → Meta.__init__(...)  初始化类对象
⑤ 结果绑定到名字 Person
```

`__prepare__` 很少用但值得见一面——它让你决定"类体在什么容器里执行"（比如收集定义顺序；如今 dict 本身有序，用处已不多）：

```python
class OrderedMeta(type):
    @classmethod
    def __prepare__(mcls, name, bases, **kwargs):
        print("__prepare__: 类体执行之前，提供命名空间")
        return {}

    def __new__(mcls, name, bases, ns, **kwargs):
        print("__new__: 类体执行完，ns =", list(ns))
        return super().__new__(mcls, name, bases, ns, **kwargs)

class Foo(metaclass=OrderedMeta):
    x = 1

# __prepare__: 类体执行之前，提供命名空间
# __new__: 类体执行完，ns = ['__module__', '__qualname__', '__firstlineno__', 'x', '__static_attributes__']
```

（`ns` 里那些双下划线键是解释器自动塞的；`__firstlineno__`、`__static_attributes__` 是 Python 3.13 新增。）

## 4. 自定义元类：三个钩子各管一段

最小模板——元类必须继承 `type`：

```python
class Meta(type):
    def __new__(mcls, name, bases, ns, **kwargs):
        # 类对象"出生前/出生中"：改 ns、检查类体、决定要不要造这个类
        return super().__new__(mcls, name, bases, ns, **kwargs)

    def __init__(cls, name, bases, ns, **kwargs):
        # 类对象"刚出生"：注册、登记、往类上挂东西
        super().__init__(name, bases, ns, **kwargs)

    def __call__(cls, *args, **kwargs):
        # 有人写 cls(...) 实例化时：拦截实例的创建过程
        return super().__call__(*args, **kwargs)
```

三个钩子和两层生命周期的对应关系（这就是把 `__init__与__new__的区别.md` 那张表往上抬一层）：

| 层面 | "实例"是谁 | `__new__` | `__init__` | `__call__` |
|---|---|---|---|---|
| 实例层（普通类） | 对象 | 造对象 | 初始化对象 | `obj()` 调用对象 |
| 类层（元类） | 类 | 造类 | 初始化类 | `MyClass(...)` 实例化 |

分工记法：

- **元类 `__new__`**：还能看到原始的 `ns` 字典 → 适合"改类体"（收集字段、改方法、加属性，改完再生）
- **元类 `__init__`**：类已成型 → 适合"登记造册"（进注册表、做校验）
- **元类 `__call__`**：每次 `MyClass(...)` 都会进来 → 适合"控制实例化"（单例、对象池、参数缓存）

跑一遍三个钩子的触发时机：

```python
class Meta(type):
    def __new__(mcls, name, bases, ns, **kwargs):
        print(f"Meta.__new__: 造类 {name}")
        return super().__new__(mcls, name, bases, ns, **kwargs)

    def __init__(cls, name, bases, ns, **kwargs):
        print(f"Meta.__init__: 初始化类 {name}")
        super().__init__(name, bases, ns, **kwargs)

    def __call__(cls, *args, **kwargs):
        print(f"Meta.__call__: {cls.__name__}(...) 实例化")
        return super().__call__(*args, **kwargs)

class Person(metaclass=Meta):
    pass

Person()          # 前两行在 class 定义时输出，第三行在实例化时输出
# Meta.__new__: 造类 Person        ← 定义时，一次性
# Meta.__init__: 初始化类 Person   ← 定义时，一次性
# Meta.__call__: Person(...) 实例化 ← 每次实例化都来
```

**注意：元类逻辑发生在"类定义时"（import 时），只跑一次**；不像装饰器模式每次调用都触发。这是元类"定义期元编程"与装饰器"运行期元编程"的本质区别。

### 坑：class 语句的额外关键字参数必须被元类"吃掉"

`class Foo(Base, metaclass=Meta, extra=1)` 里的 `extra` 会一路传给元类的 `__new__`/`__init__`，但如果你写 `**kwargs` 再原样转发给 `super().__new__(..., **kwargs)`，`type.__new__` 会把它转给**父类的 `__init_subclass__`**，而 `object.__init_subclass__` 不收额外参数，直接 `TypeError`。正确做法是元类显式接住它：

```python
class Meta(type):
    def __new__(mcls, name, bases, ns, extra=None, **kwargs):  # ← 吃掉 extra
        return super().__new__(mcls, name, bases, ns, **kwargs)
```

（这个参数机制正是 `__init_subclass__(cls, **kwargs)` 的上游：父类通过它接收子类 class 语句里的关键字参数。）

## 5. 元类编程实战四大场景

### 5.1 场景一：子类自动注册（插件系统）

需求：写完一个插件类，自动进入注册表，框架按名字取用，不需要手动 `register()`：

```python
PLUGINS = {}

class PluginMeta(type):
    def __new__(mcls, name, bases, ns):
        cls = super().__new__(mcls, name, bases, ns)
        if bases:                          # bases 为空 = 基类自己，跳过不注册
            PLUGINS[ns.get("name", name)] = cls
        return cls

class Plugin(metaclass=PluginMeta):
    pass

class ZipPlugin(Plugin):
    name = "zip"

class GzipPlugin(Plugin):
    pass                                   # 没写 name，用类名兜底

print(sorted(PLUGINS))                     # ['GzipPlugin', 'zip']
```

要点：**`bases` 为空说明是定义基类本身**，几乎所有元类模板都要有这个判断。

### 5.2 场景二：ORM 字段收集（Django/peewee Model 的原理）

需求：类里声明字段，元类在造类时把它们收集成 `_fields`，实例化时按声明做类型校验。这正好和本章的**描述符**接上——字段是描述符（管属性访问校验），元类是收集器（管定义期登记）：

```python
class Field:
    """描述符：管属性读写的校验"""
    def __init__(self, dtype, required=False):
        self.dtype = dtype
        self.required = required
        self.storage_name = None           # 由元类回填

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
        for base in bases:                 # 先继承父类已收集的字段
            fields.update(getattr(base, "_fields", {}))
        for key, val in ns.items():        # 再收集本类新声明的字段
            if isinstance(val, Field):
                val.storage_name = key     # 回填字段名给描述符用
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
print(u.to_dict())            # {'name': 'Tom', 'age': 18}
User(name=123)                # TypeError: name 需要 str
User(age=1)                   # TypeError: 缺少必填字段: ['name']
```

这就是 `Django Model` / `peewee` / `SQLAlchemy declarative` 的核心套路：**字段在"定义期"被元类收集成映射表，运行期拿它生成 SQL、做校验**。为什么 `Model` 不用 `__init__` 里遍历 `__dict__` 收集？因为那要等到每次实例化才收集，而元类让收集只发生一次、且发生在类定义时。

### 5.3 场景三：单例（对比类 `__new__` 版单例）

上一份文档用类 `__new__` 写过单例，元类版把拦截点再抬一层：

```python
class SingletonMeta(type):
    _instances = {}                        # 放元类上，所有被管的类共享一张表

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

class Config(metaclass=SingletonMeta): pass
class Logger(metaclass=SingletonMeta): pass

print(Config() is Config())     # True
print(Config() is Logger())     # False —— 表以 cls 为键，各类各管各的单例
```

对比：类 `__new__` 版只对单个类生效；元类版**一处逻辑管 N 个类**，且拦截发生在 `type.__call__` 层，连实例层 `__new__`/`__init__` 都被完整罩住。注意 `_instances` 放元类上、以 `cls` 为键，避免了"放类属性上被子类共享"的经典坑。

### 5.4 场景四：接口强制检查（定义期报错，不用等运行）

```python
class APIMeta(type):
    REQUIRED = ("run", "name")

    def __new__(mcls, name, bases, ns):
        if bases:                          # 排除基类自身
            for member in APIMeta.REQUIRED:
                if member not in ns and not any(hasattr(b, member) for b in bases):
                    raise TypeError(f"{name} 缺少必需成员: {member}")
        return super().__new__(mcls, name, bases, ns)

class API(metaclass=APIMeta):
    pass

class GoodAPI(API):
    name = "good"
    def run(self): return "ok"

class BadAPI(API):                         # ← 定义这一行当场报错：
    name = "bad"                           # TypeError: BadAPI 缺少必需成员: run
```

好处是**错误在 import 时就炸**，而不是等测试跑到一半才发现子类忘了实现方法。

## 6. 元类的确定顺序与冲突

一个类只能有一个元类。确定规则与冲突规则：

1. 显式 `metaclass=...` 最优先；
2. 没写就看基类：取**所有基类元类中最派生（最具体）的那个**；
3. 什么都没有才是 `type`。

由此推出冲突条件：如果两个基类的元类互不构成继承关系，就没法统一：

```python
class MetaA(type): pass
class MetaB(type): pass

class A(metaclass=MetaA): pass
class B(metaclass=MetaB): pass

class C(A, B): pass
# TypeError: metaclass conflict: the metaclass of a derived class must be
#            a (non-strict) subclass of the metaclasses of all its bases
```

报错信息本身就是解法：让新元类**继承所有涉事元类**（`class MetaC(MetaA, MetaB)`），再显式指定给派生类。两条铁律：元类必须是 `type` 的子类；且必须是所有基类元类的（非严格）子类。

## 7. 要不要用元类：三个工具的选择

Python 3.6 之后，很多元类场景有了更轻的替代品：

| 工具 | 时机 | 能拿到什么 | 适用 |
|---|---|---|---|
| `__init_subclass__` | 类定义时 | 子类自己的钩子 | 注册、校验、字段收集（最常见需求） |
| 类装饰器 | 类定义后 | 整个类对象 | 事后改造/包装一个类 |
| **元类** | 类定义时 + 每次实例化 | 类体字典 + `__call__` 拦截实例化 | 控制**实例化行为**、约束一整族类的元类身份 |

`__init_subclass__` 版的插件注册，效果与 5.1 完全等价且不需要继承 `type`：

```python
PLUGINS = {}

class Plugin:
    def __init_subclass__(cls, *, plugin_name=None, **kwargs):
        super().__init_subclass__(**kwargs)
        PLUGINS[plugin_name or cls.__name__] = cls

class ZipPlugin(Plugin, plugin_name="zip"): pass
class GzipPlugin(Plugin): pass

print(sorted(PLUGINS))   # ['GzipPlugin', 'zip']
```

选型建议：**能 `__init_subclass__` 就不用元类；只有需要拦截 `MyClass(...)` 实例化本身（单例/对象池）、或需要多框架协作统一元类时，才上元类**。Tim Peters 的名言依然适用：

> 如果你不确定自己需不需要元类，那你就不需要。（If you're not sure whether you need metaclasses, you don't.）

## 8. 常见坑清单

1. **额外关键字参数没被元类吃掉** → `object.__init_subclass__() takes no keyword arguments`（见第 4 节）。
2. **metaclass conflict**：多继承的两个基类元类互不相关 → 新元类继承所有涉事元类（见第 6 节）。
3. **忘了 `if bases:` 跳过基类** → 基类自己也被注册/校验，通常不是你想要的。
4. **改东西的位置选错**：要改"类体内容"在元类 `__new__` 里改 `ns`；要挂"类属性"在 `__init__` 里 `cls.xxx = ...`；要拦"实例化"必须用 `__call__`，写在 `__new__`/`__init__` 里拦不住。
5. **单例状态放错地方**：`_instances` 放元类上以 `cls` 为键是对的；放被管理的类上会被子类继承共享，出诡异 bug。
6. **元类逻辑只在定义期跑一次**：别指望它每次调用都触发（那是装饰器/描述符/`__call__` 的事）。

## 9. 记忆口诀

把三层套娃想成**"工地—房子—图纸"**：`Dog()` 是盖一间房（实例层 `__new__`/`__init__`），`class Dog` 是造一张图纸（类层），而**元类就是画图纸的那台机器（`type`）**。

- 类是元类的实例；`class` 语句 = 跑类体攒字典 → 调元类 `type` 造类
- 元类 `__new__`/`__init__` 管"造类"（定义期，一次），元类 `__call__` 管"实例化"（运行期，每次）
- 收集字段、注册子类 → `__new__`/`__init_subclass__`；拦单例、控实例化 → 元类 `__call__`
- 拿不准要不要元类 = 不需要

## 附：本文配套验证

运行 `basic/chapter08/metaclass_demo.py` 可复现本文全部示例输出（10 组用例：类是对象、type 动态建类、三钩子触发时机与 kwargs 坑、插件注册、ORM 字段收集、元类单例、接口检查、metaclass conflict、`__init_subclass__` 等价实现、`__prepare__`）。
