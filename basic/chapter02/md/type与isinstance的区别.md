# type() 与 isinstance() 的区别

> 章节：chapter01 · Python 类型检查基础
> 配套代码：`../type_test.py`（本目录可运行验证脚本）
> 配套图示：`type_object_class的关系.png`（type / class / object 关系图）

## 一句话结论

- `type(x)`：返回对象的**精确类型**（等价 `x.__class__`），只认类型本身，**不做继承判断**。
- `isinstance(x, T)`：检查对象是否属于 `T` 及其整个继承链（MRO）上的任一类型，**子类实例也命中**。

> `type` 问的是"你具体是哪个类"，`isinstance` 问的是"你算不算这一类（含它的所有子类）"。

---

## 1. type()：精确类型

### 1.1 行为

| 对象 | `type(...)` 返回 | 说明 |
|---|---|---|
| 内置值 | `type(1)` → `int`、`type("str")` → `str` | 字面量的精确类型 |
| 实例 | `type(Student())` → `Student` | 实例所属的类 |
| 类 | `type(Student)` → `type` | 类的元类（`type -> class -> obj` 链顶端） |
| 元类本身 | `type(type(Student))` → `type` | type 的类型还是 type |

### 1.2 代码

```python
class Student:
    pass

class MyStudent(Student):
    pass

s = MyStudent()
type(s)             # <class '__main__.MyStudent'>  实例的精确类
type(s) is Student  # False  子类实例不命中基类
type(Student)       # <class 'type'>  类的元类
type(type(Student)) # <class 'type'>
```

### 1.3 特性与局限

| 特性 | 说明 |
|---|---|
| 等价关系 | `type(x)` 与 `x.__class__` 通常等价；`type` 走类型系统内部，更可靠 |
| 继承判断 | **不做**。子类实例对基类返回 False |
| 多类型元组 | 不支持，需自行写 `type(x) in (int, float)` |
| ABC 虚子类 | 不识别（`__instancecheck__` 不生效） |
| 适用场景 | 必须"精确类型"：排除 bool、判断同一精确类型 |

---

## 2. isinstance()：继承链检查

### 2.1 机制

- 沿对象的类及其 MRO（`__mro__`）**向上遍历**：`MyStudent -> Student -> object`，任一命中即返回 True。
- 第二参数必须是**类型**或**类型组成的元组**；传实例会抛 `TypeError`。

### 2.2 代码

```python
isinstance(s, MyStudent)         # True
isinstance(s, Student)           # True  沿 MRO 命中基类
isinstance(s, object)            # True

isinstance(3.14, (int, float))   # True  元组支持

from collections.abc import Iterable
isinstance([1, 2], Iterable)     # True  ABC 虚子类

isinstance(True, int)            # True  bool 是 int 的子类
```

### 2.3 特性

| 特性 | 说明 |
|---|---|
| 继承链 | 沿 MRO 向上，子类实例命中基类 |
| 多类型 | 原生支持元组 `(int, float)` |
| ABC | 支持虚子类（`Iterable`、`Number` 等） |
| bool 特例 | `isinstance(True, int)` 为 True（bool 是 int 的子类） |
| 第二参数 | 必须是类型或类型元组，否则 `TypeError` |

---

## 3. 行为对比表

| 对比维度 | `type(x)` | `isinstance(x, T)` |
|---|---|---|
| 返回/结果 | 类型对象 | 布尔值 |
| 继承判断 | 不做，子类不命中基类 | 沿 MRO 检查，子类命中基类 |
| 多类型判断 | 需自行 `type(x) in (T1, T2)` | 原生支持 `(T1, T2)` 元组 |
| ABC 虚子类 | 不识别 | 识别（`__instancecheck__`） |
| bool 与 int | `type(True) is int` → False | `isinstance(True, int)` → True |
| 第二参数 | 无（只有一个参数） | 必须是类型或类型元组 |
| 典型场景 | 必须精确类型 | 常规类型检查（首选） |

---

## 4. 三个经典"看似相同、结果不同"的场景

### 4.1 bool 与 int

```python
type(True) is int        # False  bool 是独立类型
isinstance(True, int)    # True   bool 是 int 的子类
```

函数签名要求严格 `int`（如数据库主键、序列化字段）时，可用 `type(x) is int` 把 bool 挡在门外。

### 4.2 抽象基类（ABC）虚子类

```python
from collections.abc import Iterable

type([]) is Iterable     # False  list 并不是 Iterable 的"子孙类"
isinstance([], Iterable) # True   ABC 虚子类注册 / __instancecheck__
```

`isinstance` 能识别 `collections.abc`、`numbers.Number` 等虚子类，`type` 不能。判断"是否可迭代""是否数字"请用 `isinstance(x, (Iterable,))`、`isinstance(x, numbers.Number)`。

### 4.3 多类型判断

```python
# type 的写法：手动 in 元组
type(x) in (int, float)

# isinstance 的写法：原生元组
isinstance(x, (int, float))
```

---

## 5. 延伸：类视角 —— type(cls) vs __bases__ vs __mro__

`type` 与 `__bases__` 指向完全不同的方向：

| 查询 | 方向 | 语义 | 结果 |
|---|---|---|---|
| `type(cls)` | 向上 | 谁创建了我（元类） | 默认 `type`，自定义元类时返回元类 |
| `cls.__bases__` | 横向 | 我直接继承谁（基类） | 直接基类元组，多继承多元素 |
| `cls.__mro__` | 完整链 | 完整的继承顺序 | 如 `(B, A, object)` |

### 5.1 代码

```python
class Meta(type):
    pass

class A:
    pass

class B(A, metaclass=Meta):
    pass

b = B()

type(b)     # <class '__main__.B'>    实例的类型（第 1 章主题）
type(B)     # <class '__main__.Meta'> B 的元类：谁创建了 B
B.__bases__ # (<class '__main__.A'>,) 直接父类（注意是元组）
B.__mro__   # (B, A, object)         完整继承链，isinstance/super 都基于它
```

### 5.2 动态建类：type 与 __bases__ 的唯一"同框"点

```python
B2 = type('B2', (A,), {})   # 等价于 class B2(A)
B2.__bases__                # (A,)
```

动态创建类时 `type(name, bases, namespace)` 的**第二个参数就是 `__bases__`**——一个是"创建时传入"，一个是"创建后查询"，指向同一份继承信息，但语义不同。

### 5.3 三层视角示意

```
   [ Meta(type) ]           ← type(B)：B 的元类（向上看，谁创建了我）
        │
   [ object ]
   [ class A  ]             ← B.__bases__ = (A,)：直接父类（横向看）
   [ class B(A) ]           ← B.__mro__ = (B, A, object)：完整链
        │ 实例化
   [ b = B() ]              ← type(b) = B：实例的精确类型
```

### 5.4 与 isinstance 的关系

`isinstance`、`super()`、方法解析全部基于 `__mro__`，而不是 `__bases__`。`__bases__` 只列**直接**父类，多级继承时不要拿它当完整链。

---

## 6. 选型建议

1. **默认用 `isinstance`**：符合"子类即基类"的面向对象语义，支持 ABC 接口判断，是常规类型检查的首选。
2. **必须"精确类型"时才用 `type`**：
   - 排除子类混入（签名要求严格基类）；
   - 排除 bool（`type(x) is int`）；
   - 判断两个对象是否同一精确类型（`type(a) is type(b)`）。
3. **接口/能力判断用 ABC**：`isinstance(x, collections.abc.Iterable)` 比 `type(x) is list` 更通用（tuple、set、生成器都可迭代）。
4. **同一精确类型的比较用 `is` 而非 `==`**：类对象是单例，身份比较更严谨。

## 7. 常见坑

1. `isinstance(x, int)` 会命中 bool（True/False），业务上需要排除时改用 `type(x) is int`。
2. `isinstance` 第二参数传实例（如 `isinstance(x, s)`）会抛 `TypeError`，必须是类型或类型元组。
3. `__bases__` 只是**直接**父类，完整链要看 `__mro__`。
4. 实例没有 `__bases__` 属性，`b.__bases__` 会 `AttributeError`。
5. 判断类型是否相等用 `is`（身份比较），不要用 `==`（值比较对类对象虽可用，但语义不严谨）。
