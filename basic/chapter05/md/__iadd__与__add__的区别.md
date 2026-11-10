# Python 增强赋值：`__iadd__` 与 `__add__` 的区别

> 存放位置：`basic\chapter05\md\__iadd__与__add__的区别.md`
> 前置知识：特殊方法（魔法函数）机制、可变与不可变对象、运算符重载（chapter03 常用魔法函数总结）
> 配套验证：本文所有代码均在 `D:\python\fastapi_test\.venv`（Python 3.13）实测通过

## 一句话结论

**`__iadd__(self, other)` 是 `+=` 的底层方法（原地加法，in-place addition）**：类型定义了它，`x += y` 就地修改 `x` 并返回 `self`；没定义时，`+=` 自动回退成 `x = x + y`（走 `__add__`/`__radd__`），把变量**重新绑定到一个新对象**。

**不可变 ≠ 不能做运算**：`__add__` 的契约是"不修改自己、返回新对象"，所以 int/str/tuple 等不可变类型实现它完全安全；不可变类型真正不能有的是 `__iadd__`（它要求修改自身状态）。

---

## 1. 核心机制：`x += y` 的调度顺序

```
x += y
├─ ① type(x).__iadd__(x, y) 存在？ → 就地修改，x 绑定返回值（通常仍是原对象）
└─ ② 不存在或返回 NotImplemented → x = x + y
       ├─ type(x).__add__(x, y) → 新对象
       ├─ 否则 type(y).__radd__(y, x) → 新对象
       └─ 都没有 → TypeError
```

要点：**"`+=` 一定原地"是错的**。对可变对象（list 等）通常原地；对不可变对象（tuple/int/str）必然回退并产生新对象。

## 2. `__add__` vs `__iadd__` 对比表

| 维度 | `__add__`（`+`） | `__iadd__`（`+=`） |
|---|---|---|
| 语义 | 生成**新对象** | **就地修改**并返回 self |
| 原对象 | 不变 | 改变 |
| 适合 | 所有类型（尤其不可变：int/str/tuple） | 仅可变类型（list/set/dict/自定义类） |
| 变量绑定 | 必然重新绑定 | 通常不变（除非实现返回了新对象） |
| 是否要求对象可变 | 否 | 是 |

## 3. 关键辨析：不可变类型为什么有 `__add__` 而没有 `__iadd__`

实测（Python 3.13）：

```python
print("tuple 有 __add__ 吗:", hasattr(tuple, "__add__"), "| 有 __iadd__ 吗:", hasattr(tuple, "__iadd__"))
print("int   有 __add__ 吗:", hasattr(int, "__add__"), "| 有 __iadd__ 吗:", hasattr(int, "__iadd__"))
print("str   有 __add__ 吗:", hasattr(str, "__add__"), "| 有 __iadd__ 吗:", hasattr(str, "__iadd__"))
print("list  有 __add__ 吗:", hasattr(list, "__add__"), "| 有 __iadd__ 吗:", hasattr(list, "__iadd__"))
```

输出：

```
tuple 有 __add__ 吗: True | 有 __iadd__ 吗: False
int   有 __add__ 吗: True | 有 __iadd__ 吗: False
str   有 __add__ 吗: True | 有 __iadd__ 吗: False
list  有 __add__ 吗: True | 有 __iadd__ 吗: True
```

解释：

1. **`__add__` 与不可变完全不冲突**：它从头到尾不碰原对象。`1 + 2` 返回新 int、`"a" + "b"` 返回新 str、`t1 + (3,)` 返回新 tuple——原对象一个字节都没动。不可变类型实现它是最安全的。
2. **不可变类型真正不能有的是 `__iadd__`**：`+=` 要求"就地改自己再还给我"，而 int/str/tuple 内部状态不可变，无法满足，所以干脆不定义。
3. **`t += (3,)` 发生了什么**：tuple 没有 `__iadd__` → 回退 `__add__` → 生成新 tuple → 变量名 `t` 重新绑定到新对象。**原来的 tuple 对象自始至终没被修改**——"看起来变了"只是名字换了个对象。

```python
t1 = (1, 2)
t2 = t1 + (3,)
print(t1)            # (1, 2)        ← 原对象未变
print(t2)            # (1, 2, 3)     ← 新对象
print(t1 is t2)      # False         ← 确实是两个对象
```

## 4. 完整可运行验证（含自定义类）

```python
# list 可变：+= 原地
a = [1, 2]
id_before = id(a)
a += [3]
print("list 原地:", id(a) == id_before, a)      # True [1, 2, 3]

# tuple 不可变：+= 回退到 __add__，重新绑定
t = (1, 2)
id_before = id(t)
t += (3,)
print("tuple 新对象:", id(t) == id_before, t)   # False (1, 2, 3)

# 自定义类：同时定义 __add__ 和 __iadd__
class Bag:
    def __init__(self, items=None):
        self.items = list(items or [])
    def __add__(self, other):
        print("→ __add__（返回新对象）")
        return Bag(self.items + other.items)
    def __iadd__(self, other):
        print("→ __iadd__（原地修改并返回 self）")
        self.items.extend(other.items)
        return self

b = Bag([1])
b += Bag([2])
print("Bag items:", b.items)                    # [1, 2]

# 只定义 __add__：+= 自动回退
class NoIadd:
    def __init__(self, items=None):
        self.items = list(items or [])
    def __add__(self, other):
        print("→ 只有 __add__，+= 回退（返回新对象）")
        return NoIadd(self.items + other.items)

n = NoIadd([1])
n += NoIadd([2])
print("NoIadd items:", n.items)                 # [1, 2]
```

实测输出汇总：

```
list 原地: True [1, 2, 3]
tuple 新对象: False (1, 2, 3)
→ __iadd__（原地修改并返回 self）
Bag items: [1, 2]
→ 只有 __add__，+= 回退（返回新对象）
NoIadd items: [1, 2]
```

## 5. 场景与坑

### 5.1 共享引用陷阱（重要）

```python
a = [1]
b = a          # 两个名字指向同一个列表
a += [2]       # 原地修改！
print(b)       # [1, 2]  ← b 也被改了（因为 a += 没有换对象）

# 对比：a = a + [2] 则 b 不受影响（新对象）
```

`b = a; a += x` 会连带改 `b`——numpy 数组、list、DataFrame 都有此特性。若不想影响共享引用，用 `a = a + x` 或 `a = a.copy() + x`。

### 5.2 性能场景

- 循环内反复 `lst = lst + [x]`：每次创建新列表，O(n²) 累积复制。
- 循环内 `lst += [x]`（或 `lst.append(x)`）：原地扩容，均摊 O(1)。大数据量下差距显著。

### 5.3 语义选择建议

| 你的类型 | 该实现哪个 |
|---|---|
| 不可变类型（想模仿 tuple/str 语义） | 只实现 `__add__`（+ 产生新对象，+= 自动回退） |
| 可变容器（list 语义） | 两个都实现：`__add__` 返回副本，`__iadd__` 原地改并 return self |
| 惰性/链式对象（如 numpy 表达式对象） | 也可只实现 `__add__`，让 `+=` 变成"重绑新对象" |

## 6. 一句话记忆

> `__iadd__` = "原地加法"，`__add__` = "加法返回新对象"；`+=` 优先找 `__iadd__`，找不到就退回 `+`。**不可变限制的是对象内部状态，不是它能参与什么运算**——`__add__` 从不修改状态，所以它是不可变类型最欢迎的方法；`__iadd__` 才是"只有可变类型才配拥有"的方法。

## 7. 呼应章节

- chapter03 `常用魔法函数总结.md`：`__iadd__` 属于增强赋值运算符族，同类还有 `__isub__`/`__imul__`/`__itruediv__`/`__imod__`/`__ipow__`/`__iand__`/`__ior__`/`__ixor__`/`__ilshift__`/`__irshift__`/`__ifloordiv__`/`__imatmul__`。
- OOP 第 4 章 4.4/4.5（类变量/对象变量、属性查找）：`self.COUNT += 1` 的"查找后遮蔽"也是同一套运算符 + 赋值语义的体现。
- 4.8 自省：`hasattr(type, "__iadd__")` 正是用自省判断类型行为能力的手段。
