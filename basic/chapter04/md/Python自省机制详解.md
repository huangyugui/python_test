# Python 自省机制详解

> 章节：chapter04 · Python 元编程基础
> 前置知识：chapter02（`type` / `isinstance`）、chapter04（`classmethod` / `staticmethod`、多态、下划线私有约定）
> 存放位置：按项目惯例，文档归档于 chapter04/md/

## 一句话结论

**自省（introspection）指程序在运行时检查对象自身的能力**：对象是什么类型、有哪些属性与方法、函数签名长什么样、源码在哪个文件。Python"一切皆对象"+ 完全动态，自省是一等公民能力，也是 FastAPI 依赖注入、Pydantic 校验、pytest 收集用例、ORM 反射等框架机制的底层地基。

---

## 1. 什么是自省

- **定义**：程序在运行期读取自己的结构——类型、属性、方法、签名、源码、调用栈。
- **为什么 Python 特别强**：模块、类、函数、方法、实例都是对象，且元信息（`__name__`、`__dict__`、`__class__` 等）就挂在对象上，随时可查；不需要额外接口或注解。
- **自省 vs 反射**：
  - 自省 = **只读检查**（`dir`、`inspect.getmembers`、`type`）。
  - 反射 = 自省 + **运行时修改**（`setattr`、`delattr`、`type(name, bases, ns)` 动态建类）。
  - 一句话：自省是"照镜子"，反射是"照镜子 + 换衣服"。Python 社区常混用这两个词，本文聚焦自省（检查），涉及修改的见"动态属性访问"小节。

## 2. 自省手段全景

| 类别 | 手段 | 作用 |
|---|---|---|
| 类型与身份 | `type()`、`isinstance()`、`id()`、`is` | 精确类型 / 继承链检查 / 身份比较 |
| 命名空间 | `dir()`、`vars()`、`__dict__` | 列出属性、查看实例/模块命名空间字典 |
| 动态属性访问 | `getattr()`、`hasattr()`、`setattr()` | 按字符串名字读/查/写属性（反射入口） |
| 可调用判断 | `callable()` | 对象能否被调用 |
| 特殊属性 | `__name__`、`__class__`、`__module__`、`__doc__`、`__mro__`、`__bases__`、`__subclasses__()` | 名字、类型、来源、文档、继承链、子类列表 |
| 深度检查 | `inspect` 模块 | 成员枚举、函数签名、源码、文件、种类、调用栈 |

## 3. 逐类详解

### 3.1 类型与身份（chapter02 已详述，此处仅衔接）

```python
type(s) is Student        # True   精确类型
isinstance(s, Student)    # True   继承链检查
id(s)                     # 对象唯一身份标识（CPython 中为内存地址）
```

### 3.2 命名空间：dir / vars / __dict__

```python
class Student:
    def __init__(self, name):
        self._name = name

s = Student('alice')

dir(s)          # 全部属性名（含继承的、dunder，顺序不保证）
vars(s)         # {'_name': 'alice'} —— 实例命名空间字典
s.__dict__      # 与 vars(s) 相同；模块、类、实例都有 __dict__
```

- `dir()` 适合"看看这个对象能干什么"，但不适合精确枚举：含大量 `__xxx__` 噪音、顺序不保证。
- `vars()` / `__dict__` 是"真实的存储字典"——之前章节验证过 `_Student__birthday` 就在里面。

### 3.3 动态属性访问：getattr / hasattr / setattr（反射入口）

```python
getattr(s, '_name')             # 'alice'   按字符串取属性
getattr(s, 'not_exist', None)   # None      带默认值，不抛异常
hasattr(s, '_name')             # True      判断是否存在
setattr(s, 'age', 10)           # 动态添加属性（反射写操作）
```

- 注意：Python 3.2 起 `hasattr` / `getattr` **只捕获 `AttributeError`**；属性 getter 里抛出的其他异常会原样冒出，别误判为"属性不存在"。

### 3.4 特殊属性：类与函数的元信息

```python
class Student:
    """学生模型"""
    def __init__(self, name):
        self._name = name

Student.__name__          # 'Student'
Student.__qualname__      # 'Student'（嵌套类时为 'Outer.Inner'）
Student.__module__        # '__main__'
Student.__doc__           # '学生模型'
Student.__mro__           # (Student, object)  完整继承链（chapter02）
Student.__bases__         # (object,)          直接父类（chapter02）
Student.__subclasses__()  # []  直接子类列表（类自省）
s.__class__               # <class '__main__.Student'>
s.__class__.__name__      # 'Student'
```

- `__subclasses__()` 是类对象的内建自省：**不导入模块也能枚举当前已加载的直接子类**，插件/注册表场景常用。

### 3.5 inspect 模块：终极自省工具

```python
import inspect

def add(a: int, b: int = 1) -> int:
    """两数相加"""
    return a + b

inspect.isfunction(add)          # True    函数（未绑定）
inspect.ismethod(s._name.__str__)  # 判断方法
inspect.isclass(Student)         # True    判断类
inspect.ismodule(inspect)        # True    判断模块
inspect.signature(add)           # (a: 'int', b: 'int' = 1) -> 'int'  签名（含注解与默认值）
inspect.getsource(add)           # 函数的源码字符串
inspect.getfile(add)             # 源码所在文件路径
inspect.getdoc(add)              # '两数相加'  （docstring）
inspect.getmembers(s)            # [(名字, 值), ...]  全部成员
inspect.stack()                  # 当前调用栈（每帧含文件/行号/函数名）
inspect.currentframe()           # 当前执行帧
```

- 注意：`inspect.signature` 对**内置 C 函数**（如 `print`、`len`）会抛 `ValueError`，签名信息不可得。
- `inspect.isfunction` 判断的是"未绑定函数"；绑定到实例的方法要用 `inspect.ismethod`。

## 4. 自省 vs 反射（小结）

| 概念 | 动作 | 例子 |
|---|---|---|
| 自省 | 只读检查 | `type()`、`dir()`、`vars()`、`inspect.signature()` |
| 反射 | 检查 + 修改 | `setattr()`、`delattr()`、`type('X', (Base,), {...})` |
| 元编程 | 程序写程序 | 装饰器、元类、动态生成类/函数 |

## 5. 应用场景（真实世界）

1. **FastAPI 依赖注入**：路由注册时用 `inspect.signature(call)` 解析函数参数，把带默认值的 `Depends(...)` 提取出来自动装配——框架级自省，你项目的 `app/depend04.py` 就是它的用法。
2. **Pydantic**：类自省字段（v1 `__fields__` / v2 `model_fields`）驱动校验与序列化。
3. **pytest**：收集模块里 `test_*` 前缀的函数（`dir` / `getmembers` + 名字匹配）。
4. **ORM（SQLAlchemy / Peewee）**：反射数据库表结构，动态构建查询。
5. **调试与日志**：`repr()` + `vars()` + `dir()` 快速看清任意对象。
6. **插件/注册表系统**：`__subclasses__()` 或 `getattr(module, name)` 按约定发现扩展。

### 5.1 场景一：调试/日志助手（vars + type + isinstance 组合）

需求：调试时看不清对象内部结构。用自省写一个通用 `dump`，任意对象都能递归打印。

```python
def dump(obj):
    if isinstance(obj, (int, float, str, bool, type(None))):   # 原子类型
        return repr(obj)
    if isinstance(obj, list):                                 # 容器
        return "[" + ", ".join(dump(x) for x in obj) + "]"
    if isinstance(obj, tuple):
        return "(" + ", ".join(dump(x) for x in obj) + ")"
    if isinstance(obj, set):
        return "{" + ", ".join(dump(x) for x in obj) + "}"
    if isinstance(obj, dict):
        items = ", ".join(f"{k!r}: {dump(v)}" for k, v in obj.items())
        return "{" + items + "}"
    attrs = ", ".join(f"{k}: {dump(v)}" for k, v in vars(obj).items())  # 实例命名空间
    return f"{type(obj).__name__}({attrs})"

class Student:
    def __init__(self, name, scores):
        self._name = name
        self.scores = scores

print(dump(Student("alice", [90, 85])))
# Student(_name: 'alice', scores: [90, 85])
```

对应真实框架：`reprlib`、`pprint`、日志库的格式化器。

### 5.2 场景二：插件自动发现（__subclasses__）

需求：新增插件时不想手动维护注册表。用 `__subclasses__()` 自动发现已加载的直接子类。

```python
class Plugin:
    name = "base"
    def run(self): raise NotImplementedError

class LogPlugin(Plugin):
    name = "log"
    def run(self): print("写日志")

class MetricsPlugin(Plugin):
    name = "metrics"
    def run(self): print("采集指标")

for cls in Plugin.__subclasses__():   # 自动枚举，无需注册表
    print(f"发现插件: {cls.name}")
    cls().run()
# 发现插件: log / 写日志
# 发现插件: metrics / 采集指标
```

对应真实框架：Django 的 `AppConfig` 发现、各类插件体系的约定式加载。

### 5.3 场景三：pytest 式测试收集（inspect.getmembers + 前缀）

需求：自动运行模块里所有 `test_` 开头的函数——pytest 收集用例的核心思想。

```python
import inspect, sys

def run_tests(module):
    passed = 0
    for name, fn in inspect.getmembers(module, inspect.isfunction):  # 只取函数成员
        if name.startswith("test_"):
            fn()
            passed += 1
            print(f"通过: {name}")
    print(f"共 {passed} 个用例通过")

def test_add(): assert 1 + 1 == 2
def test_sub(): assert 3 - 1 == 2
def helper(): pass        # 不以 test_ 开头，不会被收集

run_tests(sys.modules[__name__])
# 通过: test_add / 通过: test_sub / 共 2 个用例通过
```

### 5.4 场景四：依赖注入（FastAPI Depends 的简化版，inspect.signature）

需求：函数声明依赖（参数注解），框架自省解析并自动注入——FastAPI 依赖注入的最小复刻。

```python
import inspect

registry = {}   # 服务注册表：类型 -> 单例

def register(cls):
    registry[cls] = cls()
    return cls

@register
class DB:
    def query(self):
        return "data"

def handler(db: DB):          # 参数注解声明依赖
    return db.query()

def resolve(fn, **overrides): # 自省解析：按注解注入
    sig = inspect.signature(fn)
    kwargs = dict(overrides)
    for name, param in sig.parameters.items():
        if param.annotation in registry:
            kwargs[name] = registry[param.annotation]
    return fn(**kwargs)

print(resolve(handler))       # data
```

对应真实框架：FastAPI 的 `Depends`、`injector`、`dependency-injector`。你项目的 `app/depend04.py` 就是 FastAPI 原生用法。

### 5.5 场景五：字段自省校验（Pydantic 思想，__annotations__）

需求：按类注解定义的"字段契约"做运行时校验——Pydantic 校验的最小复刻。

```python
class Order:
    order_id: int     # 类注解 = 字段契约
    amount: float

def validate(obj, cls):
    for field, typ in cls.__annotations__.items():
        value = getattr(obj, field)          # 动态读字段
        if not isinstance(value, typ):       # 继承链检查
            raise TypeError(
                f"{field} 应为 {typ.__name__}，实际是 {type(value).__name__}"
            )
    return True

o = Order()
o.order_id = "abc"        # 故意传错类型
o.amount = 99.5

try:
    validate(o, Order)
except TypeError as e:
    print(e)              # order_id 应为 int，实际是 str
```

对应真实框架：Pydantic v2 的 `model_validate` 与 `model_fields` 字段自省。

## 6. 常见坑

1. **hasattr 吞异常语义**：3.2 起只吞 `AttributeError`，属性 getter 抛别的异常会冒出来。
2. **dir() 不是精确清单**：顺序不保证、含大量 dunder；精确枚举用 `vars()` / `__dict__` 或 `inspect.getmembers`。
3. **inspect.signature 对 C 函数失效**：`print`、`len` 等内置函数拿不到签名，会抛 `ValueError`。
4. **自省有成本**：`dir` / `getmembers` 在热路径（如每请求循环）会拖慢性能；框架层面用缓存（FastAPI 注册时解析一次）。
5. **动态修改要克制**：滥用 `setattr` / `type()` 建类会破坏可读性、IDE 提示和静态检查（mypy/pyright），能显式就不反射。

## 7. 呼应前面章节

- `type` / `isinstance`（chapter02）：自省的入口——先知道"它是什么"。
- `__mro__` / `__bases__`：类自省；`inspect` 与 MRO 共同支撑方法查找分析。
- 下划线私有约定：自省能看到一切（`vars(s)` 里躺着 `_Student__birthday`），封装最终靠约定而非机制。
- `classmethod` 多态工厂：`cls` 本身就是自省对象——`cls.__name__`、`cls.__mro__` 随时可查。
