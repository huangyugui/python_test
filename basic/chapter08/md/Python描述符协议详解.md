# Python 描述符协议详解（descriptor protocol）

> 存放位置：`basic\chapter08\md\Python描述符协议详解.md`
> 前置知识：属性查找机制（chapter07 起）、`property`（见同章 `Python property动态属性详解.md`）、类属性与实例属性查找顺序（OOP 4.4/4.5）
> 配套验证：本文所有代码与结论均在 `D:\python\fastapi_test\.venv`（Python 3.13）实测通过

## 一句话结论

**描述符（descriptor）= 属性访问的"门卫"**：类里放一个实现了 `__get__`/`__set__`/`__delete__` 的对象，读写 `obj.attr` 时就不再直存直取，而是被这个对象接管（可校验、可计算、可映射）。有没有 `__set__` 决定门卫身份：**有 = 数据描述符（正式门卫，说了算）；没有 = 非数据描述符（临时门卫，实例字典优先）**。

---

## 1. 门卫比喻：先建立直觉

`p.age = 30`、`p.age`，表面只是"放值、取值"。但类里放的不是普通值、而是一个**门卫**时，事情就变了：

- 往里面放（赋值）→ 门卫先**检查**（不合规就拒收）
- 往外拿（读取）→ 门卫给你**加工**过的（现场算、去数据库取、类型转换）
- 要删除（`del`）→ 门卫**登记**再放行

**描述符 = 站在属性门前的门卫**。调用方 `obj.age` 的写法一个字不用改，背后的行为却能完全不同。

### 最小描述符

```python
class AgeGuard:                       # 门卫类
    def __get__(self, obj, owner):
        return obj._age               # 读取：从暗格取
    def __set__(self, obj, value):
        if value < 0:
            raise ValueError("年龄不能为负")   # 写入：先检查再存
        obj._age = value

class Person:
    age = AgeGuard()                  # 门口站了个门卫

p = Person()
p.age = 30        # 门卫检查 → 通过 → 存进 _age
print(p.age)      # 门卫从 _age 取出 → 30
p.age = -5        # ValueError: 年龄不能为负
```

门卫三技能与访问的对应：

| 你做什么 | 门卫接什么招 | 方法 |
|---|---|---|
| 读 `p.age` | 取货 | `__get__(self, obj, owner)` |
| 写 `p.age = 30` | 收货（可检查） | `__set__(self, obj, value)` |
| `del p.age` | 销货 | `__delete__(self, obj)` |

（`owner` 是宿主类；`obj` 是访问的实例，类访问时 `obj=None`。）

## 2. 属性查找完整顺序（`user.age` 的五步）

入口是 `__getattribute__`（`getattr(user, 'age')` 同路径），内部按优先级：

```
① "age" 在 User 或其基类 __dict__，且是数据描述符（有 __set__/__delete__）
        → 调用 age.__get__()          ← 最高优先，碾压实例字典
② "age" 在实例 u.__dict__
        → 直接返回 u.__dict__["age"]
③ "age" 在类 __dict__
   ③.1 是非数据描述符（只有 __get__）→ 调用 __get__()
   ③.2 普通值 → 返回 type(u).__dict__["age"]
④ 类定义了 __getattr__ → 调用 __getattr__("age")   ← 此时才轮到它
⑤ 都没有 → 抛 AttributeError
```

两个容易混的点：

- `__getattr__` 只在 `__getattribute__` 抛 `AttributeError` 后才触发（步骤④）；它和 `__getattribute__` 是**两个不同的钩子**。
- 描述符的 `__get__` 调用发生在 `__getattribute__` **内部**（步骤①③.1），不是并列关系。

## 3. 数据 vs 非数据描述符：唯一判据 + 实测

**判据：有没有 `__set__`（或 `__delete__`）。** 有 = 数据描述符；没有 = 非数据描述符。

实测差异（关键行为）：

```python
class DataDesc:                      # 数据描述符：有 __set__
    def __get__(self, obj, owner=None):
        print("DataDesc.__get__ 被调用")
        return "来自数据描述符"
    def __set__(self, obj, value):
        print("DataDesc.__set__ 被调用")
        obj._x = value

class NonDataDesc:                   # 非数据描述符：只有 __get__
    def __get__(self, obj, owner=None):
        print("NonDataDesc.__get__ 被调用")
        return "来自非数据描述符"

class User:
    age = DataDesc()                 # 数据描述符
    nickname = NonDataDesc()         # 非数据描述符
    def __init__(self):
        self.__dict__["age"] = 100           # 手动塞实例字典
        self.__dict__["nickname"] = "实例值"

u = User()
print(u.age)            # 来自数据描述符  ← 实例字典里有 100 也不看！
u.age = 20              # 走 __set__，写 _x
print(u.nickname)       # 实例值          ← 实例字典赢了
del u.__dict__["nickname"]
print(u.nickname)       # 来自非数据描述符  ← 房间空了才找门卫
```

| 维度 | 数据描述符 | 非数据描述符 |
|---|---|---|
| 判定 | 有 `__set__` 或 `__delete__` | 只有 `__get__` |
| 读 vs 实例字典 | **描述符赢** | **实例字典赢**（遮蔽） |
| 写 | 走 `__set__`，实例字典不落键 | 直接写进实例字典 |
| 内置例子 | `property`、ORM 字段、`classmethod`?（见下） | **函数/方法**、`cached_property` |

> 注：`classmethod`/`staticmethod` 也是描述符，但其 `__get__` 行为特殊（返回绑定类/原函数），分类上属于非数据描述符方向，日常不用纠结，理解"它们接管了 `obj.method` 的返回形态"即可。

## 4. 为什么这么设计：答案在"函数"身上

**Python 的每一个方法本身就是一个非数据描述符。** 这是整套设计的地基。

### 4.1 方法绑定就是描述符在干活

```python
class Person:
    def speak(self):
        return "你好"

p = Person()
p.speak()      # 你好 —— self 哪来的？
```

你写 `def speak(self)`，`p.speak()` 却自动把 `p` 传进 self。谁干的？函数的 `__get__`——它是临时门卫，在门口顺手把 `p` 绑进第一个参数，返回一个"绑定方法"（bound method）。

### 4.2 为什么函数必须是"临时"门卫（非数据）

因为要让**实例属性能覆盖方法**：

```python
p.speak = lambda: "我换个说法"      # 实例属性遮蔽类方法
print(p.speak())                    # 我换个说法
```

这就是 **monkey patch**（运行时偷换名字指向）的基础：实例级 patch 换自己、类级 patch 换大家（`Dog.speak = new_func`）、模块级 patch 换全世界（`time.sleep = fake`）。实测：类级 patch 后其他实例变、被实例覆盖过的实例不变（实例字典优先）。

如果函数是**数据**描述符（正式门卫），实例字典永远压不过类方法——你就**永远无法给单个对象定制行为**，Python 最核心的动态性直接砍掉一半。

### 4.3 反过来：为什么规则必须是"正式"门卫（数据）

校验（`property` 的 setter）、ORM 字段映射、只读控制这类规则**必须刚性执行，不允许实例字典绕过**——否则 `obj.age = "非法值"` 就能绕过所有约束。所以：

> **数据描述符 = 不可被实例覆盖的类级规则（安全、校验、映射）；非数据描述符 = 可被实例覆盖的默认行为（方法绑定、缓存、可定制点）。前者管"必须这样"，后者管"默认这样，但你可以改"。**

## 5. 业界框架都是怎么用的

| 框架/库 | 描述符 | 类别 | 用途 |
|---|---|---|---|
| 内置 | `property` | 数据 | 校验 / 只读 / 计算属性 |
| 内置 | `classmethod` / `staticmethod` | 描述符变体 | 方法绑定形态控制 |
| 内置 | `functools.cached_property`（3.8+） | 非数据 | 缓存到实例字典，`del` 即失效 |
| Django | `models.Field.__get__/__set__` | 数据 | 字段读取走数据库 / 变更追踪 |
| Django | `ManagerDescriptor` | 数据 | 防止实例覆盖 `objects` manager |
| SQLAlchemy | `InstrumentedAttribute` | 数据 | 列映射、惰性加载 |

### 5.1 cached_property 的"临时门卫"设计（最巧妙）

```python
import functools
class Calc:
    @functools.cached_property
    def heavy(self):
        print("  计算 heavy ...")
        return 42

c = Calc()
print(c.heavy)     # 计算 heavy ... / 42   ← 首次计算并塞进实例字典
print(c.heavy)     # 42                   ← 直接读房间，不再打印
del c.heavy        # 删掉实例缓存 → 失效
print(c.heavy)     # 计算 heavy ... / 42   ← 重新计算
print(c.__dict__)  # {'heavy': 42}
```

如果 `cached_property` 是数据描述符，缓存没法"删了即失效"——正因为它是**临时门卫、房间里的值优先**，"删除实例属性 = 刷新缓存"才如此自然。**"临时"不是缺点，是缓存失效机制本身。**

### 5.2 迷你 ORM（复刻 Django Field 思路）

```python
class Field:                          # 数据描述符 = ORM 字段
    def __init__(self, name): self.name = name
    def __get__(self, obj, owner=None):
        return obj.__dict__.get(self.name)      # 读走实例字典
    def __set__(self, obj, value):
        if not isinstance(value, int):
            raise TypeError(f"{self.name} 必须为 int")   # 类型校验
        obj.__dict__[self.name] = value

class User:
    age = Field("age")

u = User()
u.age = 30          # 走 __set__ 校验
u.age = "三十"      # TypeError: age 必须为 int
```

Django 的 `user.name` 之所以能触发懒加载查询，就是 `ForeignKey` 字段是数据描述符，`__get__` 里做缓存/查询；`user.name = "x"` 能变更追踪，就是 `__set__` 在记录脏字段。

## 6. 三个坑

1. **`__getattribute__` 里别忘 `super()`**：重写时 `super().__getattribute__(name)` 是底线，否则自己调自己无限递归。
2. **描述符属性名 = 存储名冲突**：门卫的 `__set__` 往 `obj.__dict__` 写**同名**键会遮蔽自己（尤其非数据描述符），惯例是存 `_x`、暴露 `x`。
3. **实例塞同名字典键 ≠ 绕过数据描述符**：`u.__dict__["age"]=100` 后读 `u.age` 仍是数据描述符的返回值（实测）；只有非数据描述符才会被实例字典盖住。

## 7. 一句话记忆

> **描述符 = 属性门卫**。有没有 `__set__` 决定身份：**有 = 正式门卫（规则说了算），没有 = 临时门卫（实例说了算）**。函数天生是临时门卫（要能被 monkey patch 覆盖），`property`/ORM 字段是正式门卫（规则不许绕过）。`cached_property` 选临时门卫，就为了让"删缓存即失效"成为天然机制。

## 8. 呼应章节

- chapter08 `Python property动态属性详解.md`：property 是数据描述符的现成实现——实例 `__dict__` 没有 `radius`、赋值走 setter，就是"正式门卫"行为。
- OOP 4.8 自省机制：`inspect.getattr_static`、`vars()` 观察实例字典，配合描述符理解"值在哪一层"。
- chapter08 拦截器主题（装饰器/代理/元类织入）：元类在类创建时改写命名空间，正是"往类字典里放门卫"的批量自动化；`__getattribute__` 是比描述符更靠前的拦截点（拦截一切属性访问，描述符只拦指定属性）。
