# Python property 动态属性详解

> 存放位置：`basic\chapter08\md\Python property动态属性详解.md`
> 前置知识：实例属性与类属性（OOP 4.4/4.5）、私有属性约定（单下划线）、描述符协议概念
> 配套验证：本文所有代码与结论均在 `D:\python\fastapi_test\.venv`（Python 3.13）实测通过

## 一句话结论

**`@property` 把"方法"伪装成"属性"**：`obj.radius` 无需括号就触发 getter 方法执行；配合 `@x.setter` / `@x.deleter` 可控制赋值与删除。本质是**数据描述符**（实现了 `__get__`/`__set__`/`__delete__`）的语法糖——让"动态计算的值"和"普通属性"用同一个 `obj.x` 语法访问，还能附带校验、只读、缓存等行为。

---

## 1. 三种用法（完整示例，已实测）

```python
class Circle:
    def __init__(self, radius):
        self._radius = radius            # 私有存储（下划线约定）

    @property
    def radius(self):                    # getter：读 c.radius
        return self._radius

    @radius.setter
    def radius(self, value):             # setter：写 c.radius = v
        if value < 0:
            raise ValueError("半径不能为负")
        self._radius = value

    @radius.deleter
    def radius(self):                    # deleter：del c.radius
        self._radius = None

    @property
    def area(self):                      # 只读计算属性（无 setter）
        return 3.14159 * self._radius ** 2

c = Circle(5)
print(c.radius)            # 5
print(round(c.area, 5))    # 78.53975   ← 每次访问现算
c.radius = 10
print(round(c.area, 5))    # 314.159

c.radius = -1              # ValueError: 半径不能为负 ← setter 校验
c.area = 100               # AttributeError: property 'area' ... has no setter
del c.radius               # 触发 deleter，_radius 置 None
```

## 2. 与普通属性的区别

| 维度 | 普通属性 | property |
|---|---|---|
| 存储 | 实例 `__dict__` 直接存值 | **不占实例存储**，每次访问执行方法 |
| 访问语法 | `obj.x` | `obj.x`（一样！） |
| 赋值 | 直接写 | 走 `__set__` → setter（可校验/拦截） |
| 删除 | `del` 删字典项 | 走 `__delete__` → deleter |
| 只读 | 无此概念 | 只写 getter → 赋值抛 AttributeError |
| 动态计算 | 需手动维护 | 每次现算（如 `area`） |
| 类型 | 存哪就在哪 | 类 `__dict__` 里是 `property` 对象 |

**存储位置实测**（关键证据）：

```
实例 __dict__: {'_radius': None}     ← 属性名 radius 不在实例字典！
类 __dict__ 含 radius: True          ← property 对象活在类字典里
类里存的是: property                 ← 类型是 property（数据描述符）
```

## 3. 原理：property 是数据描述符

`obj.x` 的属性查找顺序（描述符协议优先级）：

```
① 类型上的数据描述符（实现了 __get__ + __set__/__delete__）→ 最高优先
② 实例 __dict__
③ 类型上的非数据描述符（只有 __get__，如普通函数）
④ 类型 __dict__
```

`property` 实现了 `__get__`/`__set__`/`__delete__` 三个方法 → 是**数据描述符** → 优先级高于实例字典。所以：

- `c.radius` → 触发 `property.__get__` → 调 getter 方法 `radius(self)`。
- `c.radius = -1` → 触发 `property.__set__` → 调 setter 方法。
- 实例字典里**永远不会出现** `radius` 这个键（除非你绕过 property 直接写 `c.__dict__["radius"]=...`，但下次读还是走描述符）。

这也解释了"为什么存储用 `self._radius` 而不是 `self.radius`"——`self.radius = v` 在 setter 内部会再次触发 setter，形成无限递归。

## 4. 使用场景

| 场景 | 例子 |
|---|---|
| **校验** | setter 里拒绝负半径、非法邮箱、超长字符串 |
| **计算属性** | `area`、`full_name = first + last`、订单 `total = price * qty` |
| **只读暴露** | 内部 `_secret` 只读暴露为 `secret`（只写 getter） |
| **惰性缓存** | 首次访问才计算并缓存到 `self._cache`，之后直接返回 |
| **重构兼容** | 原来 `obj.x` 是普通属性，后来要加逻辑——改成 property 后调用方代码一行不改 |
| **隐藏内部状态** | 用 `_x` 存储、`x` 暴露，纯封装（Java 的 getter/setter 是同类需求） |

### 惰性缓存示例

```python
class Expensive:
    @property
    def data(self):
        if not hasattr(self, "_cache"):      # 首次才计算
            self._cache = [i for i in range(10**5)]   # 模拟重计算
        return self._cache                   # 之后直接返回缓存
```

## 5. 四个坑

1. **只读属性赋值**：只有 getter 没有 setter 时，赋值抛 `AttributeError`（实测信息：`property 'area' of 'Circle' object has no setter`）——这是特性不是 bug，用来做只读。
2. **setter 内部无限递归**：在 setter 里写 `self.x = v` 会再次触发 setter → `RecursionError`（实测触发）。**必须写 `self._x = v`**（存到私有名，绕开 property）。
3. **命名约定**：存储名与属性名必须区分——惯例是属性名 `x`、存储名 `_x`；如果两者同名且都用 property 逻辑，必然递归或互相遮蔽。
4. **惰性缓存失效**：手动缓存（第 4 节示例）在依赖数据变化时不会自动失效，需要显式清缓存（`del self._cache`）——property 本身不管理缓存生命周期。

## 6. Java getter/setter 对照（你的 Java 视角）

| Python | Java | 说明 |
|---|---|---|
| `@property def x` | `public int getX()` | 读取入口 |
| `@x.setter def x` | `public void setX(int v)` | 写入入口（可校验） |
| 调用 `obj.x` | 调用 `obj.getX()` | 语法不同：Python 无括号 |
| 只读：只写 getter | 只写 getX 不写 setX | 同思路 |
| 存储 `self._x` | 私有字段 `private int x` | 都藏在私有名后面 |

Java 是**显式方法调用**（`getX()`），Python 用 property 把调用伪装成**属性语法**（`obj.x`）——目标都是"数据封装 + 访问控制"，表达方式不同。

## 7. 一句话记忆

> **`@property` = 让方法长得像属性**：读走 getter、写走 setter、删走 deleter，内部存储用 `_x` 私有名。它是数据描述符，优先级高于实例字典——所以"属性名不进实例 `__dict__`，每次访问都在现算"。**要校验、要只读、要现算、要缓存，就上 property；普通直存属性永远是默认**。

## 8. 呼应章节

- OOP 第 4 章 4.4/4.5：property 是类属性（活在类 `__dict__`），查找优先级高于实例属性——正是"类属性/实例属性查找顺序"的实际应用。
- 4.7 数据封装/私有属性：`_radius` 单下划线约定 + property 暴露，是"封装"的完整姿势。
- chapter07 `可变默认参数陷阱.md`：`self._cache` 的 `hasattr` 惰性缓存与默认参数"共享/新建"问题同属对象状态管理。
