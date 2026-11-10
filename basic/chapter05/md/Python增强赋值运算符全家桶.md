# Python 增强赋值运算符全家桶：`__isub__` 到 `__imatmul__`

> 存放位置：`basic\chapter05\md\Python增强赋值运算符全家桶.md`
> 前置知识：`__iadd__` 与 `__add__` 的区别（`basic\chapter05\md\__iadd__与__add__的区别.md`）、可变与不可变对象
> 配套验证：本文所有内建类型示例均在 `D:\python\fastapi_test\.venv`（Python 3.13）实测通过；numpy 未安装，`@=` 部分标注为未实测

## 一句话结论

这 12 个方法与 `__iadd__` **共享同一套机制**：`x <op>= y` 时，Python 先找 `type(x).__i<op>__(x, y)`——有就**原地修改并返回 self**；没有就回退到普通运算 `x = x <op> y`（`__<op>__`/`__r<op>__`），产生**新对象**并重新绑定变量。**可变类型支持原地版，不可变类型一律回退**。

## 1. 全家桶对照表

| 方法 | 运算符 | 语义 | 回退到的普通方法 | 常见支持者 |
|---|---|---|---|---|
| `__iadd__` | `+=` | 原地加 | `__add__` / `__radd__` | list（extend）、set、numpy |
| `__isub__` | `-=` | 原地减 | `__sub__` / `__rsub__` | **set**（原地差集）、numpy |
| `__imul__` | `*=` | 原地乘 | `__mul__` / `__rmul__` | **list**（原地重复）、numpy |
| `__itruediv__` | `/=` | 原地真除法 | `__truediv__` | numpy |
| `__ifloordiv__` | `//=` | 原地整除 | `__floordiv__` | numpy |
| `__imod__` | `%=` | 原地取模 | `__mod__` | numpy |
| `__ipow__` | `**=` | 原地幂 | `__pow__` | numpy |
| `__iand__` | `&=` | 原地按位与 | `__and__` | **set**（原地交集）、numpy |
| `__ior__` | `\|=` | 原地按位或 | `__or__` | **set/dict**(3.9+)（原地并集/合并）、numpy |
| `__ixor__` | `^=` | 原地按位异或 | `__xor__` | **set**（原地对称差）、numpy |
| `__ilshift__` | `<<=` | 原地左移 | `__lshift__` | numpy |
| `__irshift__` | `>>=` | 原地右移 | `__rshift__` | numpy |
| `__imatmul__` | `@=` | 原地矩阵乘 | `__matmul__` | numpy（矩阵专用） |

规律一句话：**`i` 前缀 = in-place**；加、减、乘、除、幂、位运算、位移、矩阵乘——算术运算符有几个普通版，就有几个对应的 `i` 版。

## 2. 统一调度机制

```
x <op>= y
├─ ① type(x).__i<op>__(x, y) 存在？ → 原地修改，x 绑定返回值（通常仍是原对象）
└─ ② 不存在或返回 NotImplemented → x = x <op> y
       ├─ type(x).__<op>__(x, y) → 新对象
       ├─ 否则 type(y).__r<op>__(y, x) → 新对象
       └─ 都没有 → TypeError
```

## 3. 内建类型实测（Python 3.13）

```python
# ===== set：原地集合运算（-= &= |= ^= 全部原地）=====
s = {1, 2}
s_ref = s
s |= {3}
print(s, s is s_ref)        # {1, 2, 3} True   ← 同一对象，原地并入

s2 = {1, 2, 3}
s2 -= {2}
s2 &= {2, 3, 4}
print(s2)                   # {3}              ← 先差集后交集

# ===== list：*= 原地重复 =====
a = [1, 2]
b = a
a *= 2
print(a, a is b)            # [1, 2, 1, 2] True ← 原地扩展

# ===== int：一律回退（新对象）=====
n = 10
id0 = id(n)
n -= 3; n *= 2; n //= 3; n **= 2; n %= 7
print(n, id(n) != id0)      # 2 True            ← 每次运算都是新 int

# ===== 不可变类型都没有 __i<op>__ =====
for typ in (int, str, tuple):
    print(typ.__name__, "有 __isub__:", hasattr(typ, "__isub__"))
# int 有 __isub__: False
# str 有 __isub__: False
# tuple 有 __isub__: False
```

实测输出：

```
{1, 2, 3} True
{3}
[1, 2, 1, 2] True
2 True
int 有 __isub__: False
str 有 __isub__: False
tuple 有 __isub__: False
```

结论清晰：**set/list 是可变的 → 有原地版；int/str/tuple 不可变 → 一个 `__i<op>__` 都没有，全部回退**。

⚠️ 但注意：**"可变 → 一定有原地版"也是错的**——list 可变却没有 `__isub__`，原因见下一节。

## 4. 为什么 list 没有 `__isub__`：i 版永远跟随普通版

**核心逻辑**：`__isub__` 只是 `__sub__` 的"原地优化版"——list 连普通减法 `__sub__` 都没有，原地版自然无从谈起。真正的问题是：为什么 list 支持 `+` 和 `*`，却不支持 `-`？

实测支持矩阵（Python 3.13）：

```
        __add__/__iadd__   __sub__/__isub__   __mul__/__imul__
list       True / True       False / False      True / True
set       False / False       True / True      False / False
tuple      True / False      False / False      True / False
str        True / False      False / False      True / False
```

原因分四层：

1. **list 的模型是"有序序列、元素可重复"**。`+` 拼接有唯一明确语义（首尾相连成新序列），`*` 重复也有唯一明确语义（序列复制 n 遍）——所以它们被实现，也自然有原地版。
2. **"list 相减"语义模糊**。`[1,2,3] - [2]` 是按值删 2？删第一个还是全部？还是按索引删？还是逐位相减？——每一种都有道理，没有唯一的自然答案。给运算符配上含糊语义，代码就不可读了。
3. **差集概念来自 set，不是 list**。数学上的"差"定义在**无序、无重复**的集合上（`set` 是数学集合的直接映射），所以 `set` 有 `-`/`-=`（差集）且语义唯一；list 不是集合，硬套差集是错位。
4. **Python 哲学：explicit is better than implicit（显式优于隐式）**。模糊的运算宁可缺省，逼你用显式手段表达意图：

```python
a = [1, 2, 2, 3]
a.remove(2)    # 按值删第一个 → [1, 2, 3]
del a[0]       # 按索引删     → [2, 3]
a = [x for x in a if x != 3]   # 按条件过滤（删全部匹配）
```

记忆锚点：

- **list 是一根绳子**：能接长（`+`）、能复制（`*`），但不能"减去一段"——剪哪段得由你说了算。
- **set 是一个集合**：数学上天生定义差（`-`）、交（`&`）、并（`|`）、对称差（`^`），四个运算符的原地版全部齐备。
- **一般规律：先问有没有普通版，再问有没有原地版**——`i` 永远跟随普通版存在。

## 5. 自定义类：完整原地实现示例

```python
class Vector:
    def __init__(self, x, y):
        self.x, self.y = x, y

    def __isub__(self, other):        # -=
        self.x -= other.x; self.y -= other.y
        return self

    def __imul__(self, scalar):       # *=
        self.x *= scalar; self.y *= scalar
        return self

    def __itruediv__(self, scalar):   # /=
        self.x /= scalar; self.y /= scalar
        return self

    def __ipow__(self, exp):          # **=
        self.x **= exp; self.y **= exp
        return self

    def __str__(self):
        return f"Vector({self.x}, {self.y})"

v = Vector(10, 4)
v -= Vector(1, 1)    # 原地减
v *= 2               # 原地乘
v /= 3               # 原地除
v **= 2              # 原地幂
print(v)             # Vector(36.0, 4.0)
```

实测输出：`Vector(36.0, 4.0)` —— 全程没有创建新对象，每次 `op=` 都修改同一个 `v` 的内部状态。

编写要点：**每个 `__i<op>__` 必须 `return self`**（除非你想让变量重新绑定），这与 `__add__` 返回新对象形成对照。若只实现普通版不实现 `i` 版，`op=` 会自动回退成"新建对象 + 重绑变量"。

## 6. 场景与坑

### 6.1 共享引用陷阱（与 `__iadd__` 完全一致）

```python
s = {1, 2}
t = s          # 两个名字指向同一个 set
s |= {3}       # 原地并入
print(t)       # {1, 2, 3}  ← t 也被改了

a = [1, 2]
b = a
a *= 2
print(b)       # [1, 2, 1, 2] ← b 也被改了
```

只要对象可变且支持原地版，`b = a; a op= x` 就会连带影响 `b`。不想共享就用 `a = a op x` 或 `a = a.copy()` 后运算。

### 6.2 不同容器的 `+=`/`*=` 语义差别

| 容器 | `a += b` | `a *= n` |
|---|---|---|
| list | 原地 `extend(b)` | 原地重复 n 次 |
| tuple | 回退新建（拼接新元组） | 回退新建 |
| str | 回退新建（拼接新字符串） | 回退新建 |
| set | 原地并入（`|=` 同义） | 不支持（`*=` 对 set 无意义） |

### 6.3 numpy 场景（未实测，标注说明）

numpy 数组（ndarray）几乎支持全部 12 个原地运算符（`+=`、`-=`、`*=`、`/=`、`//=`、`%=`、`**=`、`&=`、`|=`、`^=`、`<<=`、`>>=`、`@=`），且 `@=` 是**矩阵乘法**专用的原地版（对应 `__imatmul__`）。本项目 .venv 未安装 numpy，故 `@=` 未实测；了解即可：`np.matmul(a, b)` 的原地版就是 `a @= b`。

## 7. 一句话记忆

> 算术/位运算家族每个普通方法（`__add__`、`__sub__`…）都配一个 `i` 前缀的原地版（`__iadd__`、`__isub__`…），对应 `+=`、`-=`… 运算符。**可变类型实现原地版，不可变类型自动回退新建**；共享引用时原地版会连带修改所有别名。

## 8. 呼应章节

- chapter05 `__iadd__与__add__的区别.md`：本文件的机制母版（调度顺序、共享引用、性能建议均同源）。
- OOP 第 4 章 4.4/4.5：`self.COUNT += 1` 的"查找后遮蔽"同样是增强赋值 + 属性查找链的组合。
- 4.8 自省：`hasattr(list, "__isub__")` 这类检查，就是判断一个类型"支持哪些原地运算"的标准手段。
