# `__init__` 与 `__new__` 的区别

一句话概括：**`__new__` 负责"创建"实例，`__init__` 负责"初始化"实例**。调用 `MyClass(参数)` 时，先执行 `__new__`，成功拿到实例后再执行 `__init__`。

## 对比总览

| 对比点 | `__new__` | `__init__` |
|---|---|---|
| 职责 | 创建并返回实例（分配对象） | 初始化实例属性（不返回值） |
| 第一个参数 | `cls`（类本身） | `self`（实例） |
| 返回值 | 必须返回一个实例 | 必须返回 `None`，返回其他值会抛 `TypeError` |
| 调用顺序 | 先调用 | 后调用 |
| 是否隐式静态方法 | 是（不用写 `@staticmethod`） | 普通实例方法 |

## 基本执行顺序

```python
class Demo:
    def __new__(cls, value):
        print("1. __new__ 被调用")
        return super().__new__(cls)   # 必须返回实例

    def __init__(self, value):
        print("2. __init__ 被调用")
        self.value = value

Demo(42)
# 输出: 1. __new__ 被调用
#       2. __init__ 被调用
```

一个重要细节：**`__new__` 的返回值决定了 `__init__` 是否被调用**。如果 `__new__` 返回的不是本类（或其子类）的实例，`__init__` 会被完全跳过：

```python
class Weird:
    def __new__(cls):
        return "我只是个字符串"   # 返回了 str，不是 Weird 实例
    def __init__(self):
        print("不会执行到这里")
```

另外，`__new__` 和 `__init__` 接收的是同一组参数（除去 `cls`/`self`），所以两者签名要保持兼容。

## 什么时候需要重写 `__new__`

日常写类只需要 `__init__`。需要动 `__new__` 的典型场景有三个：

### 1. 单例模式

```python
class Singleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

a = Singleton()
b = Singleton()
print(a is b)  # True，始终是同一个对象
```

### 2. 子类化不可变类型（`int`、`str`、`tuple` 等）

因为对象一旦创建就无法修改，必须在 `__new__` 阶段就构造出正确的值，`__init__` 里改不了：

```python
class PositiveInt(int):
    def __new__(cls, value):
        if value <= 0:
            raise ValueError("必须是正数")
        return super().__new__(cls, value)

PositiveInt(5)   # OK
PositiveInt(-1)  # ValueError
```

### 3. 需要控制"是否/如何创建对象"本身

比如对象池、缓存复用（`str` 驻留、`bool` 的 `True/False` 单例就是这么实现的）、或在元类 `__call__` 里拦截实例化。

## 记忆方式

把 `MyClass(args)` 想成两步：`__new__` 是"造出毛坯房"（返回实例），`__init__` 是"装修入住"（往 `self` 上挂属性）。没有毛坯房（`__new__` 返回的不是本类实例），装修就不进行（`__init__` 不执行）；而装修工本身不该产出新房（`__init__` 不允许有返回值）。
