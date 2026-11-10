# Python 生成器运行逻辑详解：状态机、协议与协程前身

> 存放位置：`basic\chapter12\md\Python生成器运行逻辑详解.md`
> 前置知识：迭代器协议（`__iter__`/`__next__`）、函数调用与栈帧（chapter09 `02Python生成器函数与栈帧详解.md`）、异常传播机制
> 分工说明：chapter05 `Python生成器详解.md` 讲**用途**（省内存、无限序列、Java 对照）；chapter09 讲**栈帧为什么能在堆上存活**；本文只讲一件事——**生成器被驱动时，内部到底按什么逻辑在跑**，并把它接到本章的协程上
> 配套验证：本文所有代码与输出均在 `D:\python\fastapi_test\.venv`（Python 3.13.9）实测

---

## 目录

1. [先把"逻辑"拆成两层](#一先把逻辑拆成两层)
2. [编译期：函数被改写成了什么样](#二编译期函数被改写成了什么样)
3. [运行期：四个状态的单向流转](#三运行期四个状态的单向流转)
4. [`yield` 是表达式：求值顺序决定一切](#四yield-是表达式求值顺序决定一切)
5. [三种驱动方式，一个恢复机制](#五三种驱动方式一个恢复机制)
6. [异常路径：`throw()` 的三种结局](#六异常路径throw-的三种结局)
7. [收尾：耗尽、`close()` 与 GC](#七收尾耗尽close-与-gc)
8. [`yield from`：一句委托，三路透传](#八yield-from一句委托三路透传)
9. [成本模型：快在哪，慢在哪](#九成本模型快在哪慢在哪)
10. [演进：从生成器到协程](#十演进从生成器到协程)
11. [工程要点与常见坑](#十一工程要点与常见坑)
12. [总结](#十二总结)
13. [呼应章节](#十三呼应章节)

---

## 一句话结论

**生成器不是"特殊函数"，而是一个被编译器改造过、由堆上帧支撑的显式状态机。**

- 调用生成器函数 = 只创建对象，**函数体一行都不执行**（字节码第一条是 `RETURN_GENERATOR`）；
- 每次驱动（`next` / `send` / `throw`）= **把控制权还给那个冻结的帧**，从 `f_lasti` 记录的位置继续，跑到 `YIELD_VALUE` 再冻住；
- `yield` 是**表达式而不是语句**：它先"交出值"，恢复时才"收回值"——这一个设计就让生成器从"单向产出"升级成"双向通道"，也就是协程的前身。

---

## 一、先把"逻辑"拆成两层

同一段 `yield` 代码，在编译期和运行期被两套机制处理。混在一起看，就会觉得生成器很玄。

| 阶段 | 发生了什么 | 观察手段 |
|---|---|---|
| **编译期** | 函数被标记为生成器（`co_flags` 含 `CO_GENERATOR`，实测 `0x23`），函数体首尾插入 `RETURN_GENERATOR` / `YIELD_VALUE` / `RESUME`，末尾加 PEP 479 的隐式异常处理 | `dis.dis(func)`、`func.__code__.co_flags` |
| **运行期** | 调用只建对象；每次驱动从 `gi_frame.f_lasti` 处恢复；状态单向流转 CREATED → SUSPENDED → CLOSED | `inspect.getgeneratorstate()`、`g.gi_frame` |

记住这条主线，后面所有现象都能推出来：**"暂停"的本质是帧没被销毁，"恢复"的本质是拿着 `f_lasti` 重新进入这个帧。**

---

## 二、编译期：函数被改写成了什么样

```python
def simple():
    x = 1
    yield x
    yield x + 1
```

`dis.dis(simple)` 的真实输出（3.13）：

```text
  2            RETURN_GENERATOR
               POP_TOP
       L1:     RESUME                   0
  3            LOAD_CONST               1 (1)
               STORE_FAST               0 (x)
  4            LOAD_FAST                0 (x)
               YIELD_VALUE              0
               RESUME                   5
               POP_TOP
  5            LOAD_FAST                0 (x)
               LOAD_CONST               1 (1)
               BINARY_OP                0 (+)
               YIELD_VALUE              0
               RESUME                   5
               POP_TOP
               RETURN_CONST             0 (None)
       L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
               RERAISE                  1
```

逐条读，信息量比想象中大：

| 指令 | 含义 | 对应结论 |
|---|---|---|
| `RETURN_GENERATOR` | 一进来就把生成器对象返回给调用方，后面的字节码**本次不执行** | 所以 `gen = f()` 时函数体没跑 |
| `RESUME 0` | 第一次被 `next()` 驱动时的入口 | 三种驱动方式最终都汇到 `RESUME` |
| `YIELD_VALUE` | 把栈顶值交给调用方，**帧冻结** | `yield` 是"产出点" |
| `RESUME 5` | 下次被驱动时的恢复点 | `yield` 也是"恢复点" |
| `POP_TOP` | 丢掉 `send()` 送进来的值 | 因为这里没人接收它（`yield x` 没赋值给谁） |
| `RETURN_CONST 0 (None)` | 自然结束，返回 `None` | 结束时变成 `StopIteration(None)` |
| `CALL_INTRINSIC_1 (INTRINSIC_STOPITERATION_ERROR)` + `RERAISE` | 3.11+ 用异常表实现的隐式 `try/except`，把漏出的 `StopIteration` 转成 `RuntimeError` | PEP 479 的落地位置 |

**注意 `YIELD_VALUE` 和 `RESUME` 永远成对出现。** 一对就是"一个暂停点"。`yield` 在字节码层面从来不是"返回"，而是"交出 + 等待回来"。

> 一个值得停下来想的问题：如果 `yield` 只是"返回值"，为什么它后面还要紧跟一条 `RESUME`？因为**它必须能回来**。`return` 之后没有"回来"这回事，`yield` 有——这条 `RESUME` 就是"回来"的落点。

---

## 三、运行期：四个状态的单向流转

`inspect.getgeneratorstate()` 能读到四个状态，实测：

```python
import inspect

def echo():
    while True:
        n = yield "ready"
        print("  收到:", n)

g = echo()
print(inspect.getgeneratorstate(g))   # GEN_CREATED
next(g)
print(inspect.getgeneratorstate(g))   # GEN_SUSPENDED
g.close()
print(inspect.getgeneratorstate(g))   # GEN_CLOSED
```

| 状态 | 含义 | 此时 `gi_frame` | 能不能驱动 |
|---|---|---|---|
| `GEN_CREATED` | 对象建好了，从没跑过 | 有（`f_lasti` 指向第一条 `RESUME`，实测为 2；`f_locals` 为 `{}`） | 只能 `next()` / `send(None)` |
| `GEN_RUNNING` | 正在执行中 | 有 | 不能重入，否则 `ValueError` |
| `GEN_SUSPENDED` | 停在某个 `yield` 上 | 有（保存着 `f_lasti` 和 `f_locals`） | 可以 `next`/`send`/`throw`/`close` |
| `GEN_CLOSED` | 结束、异常退出或被 close | **`None`** | 只能得到 `StopIteration` |

几个容易忽略的点：

- **`GEN_CLOSED` 时 `gi_frame` 变成 `None`**。这不是"清空了帧内容"，而是**帧被释放了**——所以关闭后再想恢复，物理上已经不可能。
- **状态是单向的**。`CREATED → SUSPENDED ⇄ RUNNING → CLOSED`，没有任何回头路。
- **`GEN_RUNNING` 在主线程里基本观察不到**，因为你能调用 `getgeneratorstate` 的时候它已经让出控制权了；它主要出现在多线程里另一个线程恰好撞见"这个生成器正在跑"。
- 3.11+ 多了 `gi_suspended` 布尔属性，等价于"状态 == GEN_SUSPENDED"，但读取更快。

实测一组状态与帧的对应关系：

```python
def trace():
    a = 1
    yield a
    b = a + 1
    yield b
    c = b * 2
    yield c

g = trace()
next(g)   # value=1, f_lasti=14, f_locals={'a': 1}
next(g)   # value=2, f_lasti=32, f_locals={'a': 1, 'b': 2}
next(g)   # value=4, f_lasti=50, f_locals={'a': 1, 'b': 2, 'c': 4}
next(g)   # StopIteration, gi_frame = None
```

`f_lasti` 一路后移，`f_locals` 一路累积——**这就是"状态被保存"的字面含义**：不是把变量拷贝到某处，而是它们本来就在这个堆上的帧里，没人销毁而已。

---

## 四、`yield` 是表达式：求值顺序决定一切

这是理解生成器"逻辑"的关键分水岭。`yield` 不是"输出语句"，它**有值**，值是下一次 `send()` 送进来的东西。

### 4.1 先交出，再收回

```python
def order():
    print("[A] 进入函数体")
    received = yield "产出值"
    print("[B] yield 表达式求值完毕, 收到:", received)
    return "返回值"

g = order()
print(g.send(None))     # [A] → 产出值
g.send("送入值")         # [B] 收到: 送入值 → StopIteration("返回值")
```

实测输出顺序：

```text
[A] 进入函数体
产出值
[B] yield 表达式求值完毕, 收到: 送入值
```

**"产出值" 在 "[B]" 之前就打印了。** 也就是说 `received = yield "产出值"` 这一行要分两次执行：

1. 第一次驱动：执行到 `yield "产出值"`，**交出 `"产出值"` 并暂停**——此时赋值还没发生；
2. 第二次驱动（`send("送入值")`）：`yield` 表达式**在此刻求值完毕**，结果是 `"送入值"`，然后才赋给 `received`。

所以 `yield` 的语义是：**「先出门送个东西，回来时手里多了个东西」**。

### 4.2 `send()` 的返回值不是函数返回值

这个坑很常见：**`send()` 返回的是"下一次 `yield` 的产出"，函数自己 `return` 的东西另走一条路。**

```python
def two_step():
    a = yield "A"
    print("函数内部收到 a =", a)
    b = yield "B"
    print("函数内部收到 b =", b)
    return "done"

g = two_step()
print(g.send(None))    # A
print(g.send("给A"))   # B   ← 注意：不是 "done"
try:
    g.send("给B")
except StopIteration as e:
    print("value =", e.value)   # done ← return 值在这里
```

| 你以为 | 实际 |
|---|---|
| `send(x)` 返回函数 `return` 的值 | 返回**下一个 `yield` 产出的值** |
| 函数 `return` 的值直接拿到 | 藏在 `StopIteration.value` 里 |

实测输出：

```text
send(None) 返回: A
send('给A') 返回: B      ← 下一个 yield 的产出
第三次 send 抛 StopIteration, value = done   ← 这才是 return 值
```

之所以这样设计：`send()` 驱动的是"跑到下一个产出点"，它能正常返回就说明**还没结束**；函数一旦结束，就没有"下一个产出"可返回了，只能靠异常（`StopIteration`）来同时表达"结束了"和"结束得值是什么"。

```text
send(None) 返回: A
send('给A') 返回: B      ← 下一个 yield 的产出
第三次 send 抛 StopIteration, value = done   ← 这才是 return 值
```

### 4.3 运算符优先级：括号不能省

既然 `yield` 是表达式，它就能参与运算——但优先级极低，必须加括号：

```python
def paren():
    x = (yield 1) + (yield 2)   # 括号不可省
    print("x =", x)

g = paren()
next(g)        # 产出 1
g.send(10)     # 产出 2
g.send(20)     # x = 30，然后结束
```

写 `x = yield 1 + yield 2` 会直接 `SyntaxError`；分两行写成 `a = yield 1` / `b = yield 2` 才是常见的正确形态。

### 4.4 首次必须"预热"（priming）

生成器刚创建时停在函数开头，**还没有挂起的 `yield` 可以接收值**：

```python
g = echo()
g.send("x")
# TypeError: can't send non-None value to a just-started generator
```

所以 `send(非None)` 之前必须 `next(g)`（或 `g.send(None)`）先跑到第一个 `yield`。`next(g)` 在语义上就等价于 `g.send(None)`——**这一点是理解"三种驱动方式其实是一种"的钥匙**。

---

## 五、三种驱动方式，一个恢复机制

| 驱动方式 | 等价于 | 恢复方式 | 典型场景 |
|---|---|---|---|
| `next(g)` / `for` 循环 | `g.send(None)` | 让挂起的 `yield` 表达式求值为 `None` | 单纯消费数据 |
| `g.send(v)` | — | 让挂起的 `yield` 表达式求值为 `v` | 双向通信、协程 |
| `g.throw(E)` | — | **在挂起点抛出异常** | 错误注入、取消 |
| `g.close()` | `g.throw(GeneratorExit)` | 在挂起点抛 `GeneratorExit` | 资源清理 |

关键洞察：**它们不是三套机制，而是"用不同方式恢复同一个帧"**。`send` 用"正常返回值"的方式恢复，`throw` 用"抛异常"的方式恢复。这正好对应函数调用的两条出路——正常返回、异常上抛。

用状态机的话说：

```text
              next()/send(None)              next()/send(v)
GEN_CREATED ──────────────────► GEN_SUSPENDED ──────────────► GEN_SUSPENDED
     │                                │                              │
     │ close()                        │ throw(e)                     │ 函数体跑完
     ▼                                ▼                              ▼
GEN_CLOSED ◄────────────────── 异常冒出或再次挂起                 GEN_CLOSED
```

---

## 六、异常路径：`throw()` 的三种结局

`g.throw(KeyError("bad"))` 在挂起点把异常抛进生成器内部，结局取决于生成器怎么处理：

```python
def with_cleanup():
    try:
        yield 1
        yield 2
    except KeyError as e:
        print("捕获 KeyError:", e)
        yield "recovered"
    finally:
        print("finally 清理")

g = with_cleanup()
next(g)                      # 1
g.throw(KeyError("bad"))     # 捕获 KeyError → 产出 "recovered"
next(g)                      # finally 清理 → StopIteration
```

| 生成器的反应 | 结果 | 状态 |
|---|---|---|
| 不捕获 | 异常从 `throw()` 调用点冒出 | `GEN_CLOSED` |
| 捕获后继续 `yield` | `throw()` **返回下一个 yield 的产出** | `GEN_SUSPENDED`（还活着） |
| 捕获后 `return` / 跑完 | 抛 `StopIteration(value)` | `GEN_CLOSED` |

第二种是重点，实测可见：

```python
def swallow_gen():
    while True:
        try:
            yield "wait"
        except ValueError:
            print("吞掉了 ValueError, 生成器继续活着")

g = swallow_gen()
next(g)
g.throw(ValueError("x"))     # 输出：吞掉了 ValueError... 返回 "wait"
inspect.getgeneratorstate(g) # GEN_SUSPENDED ← 没死
```

**异常不会自动杀死生成器**，只有"没被接住"或"接住后不打算继续"才会。

### 6.1 PEP 479：为什么生成器里的 `StopIteration` 会变成 `RuntimeError`

`StopIteration` 在 Python 里是**迭代结束的信号**。如果生成器内部随手 `raise StopIteration` 或 `next()` 一个空迭代器让它漏出去，外层 `for` 循环会误以为"这个生成器正常结束了"，而实际上函数是半路出错的。

PEP 479 的处理：**生成器内部漏出的 `StopIteration` 一律转成 `RuntimeError`**，并把原异常挂在 `__cause__` 上。

```python
def inner_raise():
    raise StopIteration("内部")

def wrapper():
    yield from inner_raise()

next(wrapper())
# RuntimeError: generator raised StopIteration
# __cause__: StopIteration('内部')
```

正确写法是显式捕获后 `return`：

```python
def safe():
    it = iter([])
    try:
        next(it)
    except StopIteration:
        return "正常结束"
    yield          # 有这个 yield，函数才是生成器
```

实测 `StopIteration.value == "正常结束"`。

> 顺带一个新手陷阱：上面函数如果只有 `return` 没有可达的 `yield`，它**根本不是生成器函数**，调用直接返回 `"我不是生成器"` 这个 `str`，`next()` 会报 `'str' object is not an iterator`。判断依据是**函数体内任何位置出现 `yield`**（哪怕不可达），而不是运行时是否执行到。

---

## 七、收尾：耗尽、`close()` 与 GC

生成器的结束方式不止一种，清理逻辑的触发条件也各不相同（注意最后两行是"还没开始就结束"的边界情况）：

| 结束方式 | 触发什么 | `finally` 是否执行 | 备注 |
|---|---|---|---|
| 自然耗尽 | `StopIteration(value)` | 执行 | `value` 是 `return` 值 |
| `g.close()` | 挂起点注入 `GeneratorExit` | 执行 | `close()` 返回 `None` |
| GC 回收 | 同 `close()` | 执行 | 引用计数归零即触发 |
| 未启动就 `close()` | 直接标记关闭 | **不执行**（函数体从未进入） | 状态直接 `GEN_CLOSED` |
| 未启动就 `throw()` | **在调用点直接抛出** | 不执行 | 状态 `GEN_CLOSED` |

实测 GC 那条最反直觉，但很重要：

```python
def with_finally():
    try:
        yield 1
        yield 2
    finally:
        print("[finally] 执行了清理")

g = with_finally()
next(g)
del g          # 引用归零
# 输出：[finally] 执行了清理
```

连循环引用也逃不掉（GC 分代回收后会调用生成器的终结逻辑）。**这就是生成器能安全管资源的前提**：不管你怎么丢，`finally` 都有人兜底。

### 7.1 `close()` 的协议：`GeneratorExit` 不能不理

`close()` 在挂起点抛 `GeneratorExit`，生成器只有两种合法反应：

- **退出**（不捕获，或捕获后 `raise` / `return`）→ 正常关闭；
- **再 `yield`** → 违反协议，`close()` 抛 `RuntimeError: generator ignored GeneratorExit`。

```python
def bad_close():
    try:
        yield 1
    except GeneratorExit:
        yield 2      # 违规

g = bad_close()
next(g)
g.close()   # RuntimeError: generator ignored GeneratorExit
```

所以写清理代码时，`except GeneratorExit` 里**只做清理，不要产出值**。日常更推荐直接写 `finally`，不用手动碰 `GeneratorExit`。

---

## 八、`yield from`：一句委托，三路透传

`yield from` 常被简化成"等价于 `for v in sub: yield v`"。**这个说法丢了 90% 的信息**：手写 `for` 只能透传"值"这一路，而 `yield from` 透传**值、异常、`return` 三路**，并自动完成启动与收尾。

### 8.1 三路透传实测

```python
def sub():
    try:
        x = yield "sub-1"
        y = yield "sub-2"
    except ValueError as e:
        yield "sub-recovered"
    return "sub-return"

def delegator():
    r = yield from sub()
    print("拿到子生成器 return 值:", r)
    return r.upper()
```

| 你对委托者做什么 | `yield from` 替你转给子生成器 | 实测结果 |
|---|---|---|
| `d.send(1)` | `sub.send(1)` → `x = 1` | 产出 `sub-2` |
| `d.throw(ValueError)` | `sub.throw(ValueError)` | 产出 `sub-recovered` |
| `sub` 执行 `return "sub-return"` | 成为 `yield from` 表达式的**值** | `r == "sub-return"`，委托者最终 `StopIteration("SUB-RETURN")` |
| `d.close()` | `sub.close()` | 委托链一起关闭，委托者状态 `GEN_CLOSED` |

手写 `for v in sub(): yield v` 版本全丢，而且**丢得很安静**——实测：

```python
def manual():
    for v in sub():
        yield v

m = manual()
next(m)          # sub-1
m.send(99)       # 返回 sub-2，但 99 去哪了？
```

结果是子生成器的 `x` 收到 `None`：`send(99)` 的值落到外层 `yield v` 的恢复点上，被 `POP_TOP` **直接丢掉**，根本没传到子生成器。同理 `throw` 打不到子生成器，`sub` 的 `return` 值被 `StopIteration` 吞掉。

**静默丢弃比报错更危险**：报错至少会提醒你写错了，静默丢弃会让协程"看起来在跑，但上级指令永远收不到"。

### 8.2 字节码真相

`yield from` 在 3.11+ 被展开成一条 `SEND` 循环：

```text
GET_YIELD_FROM_ITER
LOAD_CONST 0 (None)
SEND 3 (to L5)
YIELD_VALUE 1
RESUME 2
JUMP_BACKWARD_NO_INTERRUPT 5 (to L2)
L5: END_SEND
CLEANUP_THROW
```

`SEND` 负责"把值交给子迭代器并取回下一个产出"，`YIELD_VALUE` / `RESUME` 是透传给外层的挂起点，`END_SEND` 取回子生成器的 `StopIteration.value` 作为表达式结果，`CLEANUP_THROW` 处理 `throw` 路径。

同时解释器仍然维护 `gi_yieldfrom` 指向子生成器，实测：

```python
d = delegator()
next(d)
d.gi_yieldfrom          # <generator object sub at 0x...>
```

而手写 `for` 委托时它是 `None`——**这是运行时能区分两种写法的依据**，也是 `yield from` 不是语法糖的证据。

### 8.3 可以直接委托任意可迭代对象

```python
def flat():
    yield from [1, 2]
    yield from (3, 4)
    yield from "ab"

list(flat())   # [1, 2, 3, 4, 'a', 'b']
```

`GET_YIELD_FROM_ITER` 会先 `iter()` 一次，所以列表、字符串、字典都能接。

---

## 九、成本模型：快在哪，慢在哪

生成器不是"零成本的抽象"。实测（n = 10⁶，全量消费，`timeit` 取 5 次最小值，Python 3.13）：

| 写法 | 耗时 | 说明 |
|---|---|---|
| `sum(range(n))` | **15.81 ms** | C 层迭代，无 Python 帧参与 |
| `sum([x for x in range(n)])` | 63.84 ms | 先分配 100 万元素的 list，再求和 |
| `sum(x for x in range(n))` | 44.61 ms | 不分配容器，但每次取值走一次 `RESUME`/`YIELD_VALUE` |

结论很有教育意义：**全量消费时，生成器并不比列表推导快多少，它只是省掉了容器分配**；比 `sum(range(n))` 慢 3 倍左右，因为每个元素都要经历一次"帧切换 + 值传递"。

生成器真正的价值在**短路**和**内存**，实测对比（1000 万规模，只取前 10 个）：

| 写法 | 耗时 | 内存 |
|---|---|---|
| `islice(expensive(), 10)` | **19.0 μs** | 生成器对象 192 字节 |
| `[i*i for i in range(10**7)][:10]` | 919.9 ms | 列表先把 1000 万个 int 全部装进内存（量级数百 MB） |

**差 4 个数量级。** 所以判断标准不是"生成器更快吗"，而是：

> 你会不会只消费一部分？数据量是否超过内存？如果是，生成器赢；如果一定要全量算完再遍历，列表推导甚至 `range` 更划算。

---

## 十、演进：从生成器到协程

本章的主题是协程，而协程的每一块砖都来自生成器：

| PEP | 提出 / 落地 | 加了什么 | 意义 |
|---|---|---|---|
| PEP 255 | 2001 / 2.2 | `yield` | 生成器诞生：函数可以暂停/恢复 |
| PEP 342 | 2005 / 2.5 | `send` / `throw` / `close`，`yield` 变表达式 | 单向产出 → **双向通道**，生成器可以当协程用 |
| PEP 380 | 2009 / 3.3 | `yield from` | 委托子生成器，三路透传，协程可以分层组合 |
| PEP 3156 | 2012 / 3.4 | `asyncio` + `@coroutine` | 用生成器实现事件循环调度 |
| PEP 492 | 2015 / 3.5 | `async` / `await` | 原生协程：语法层面区分"生成器"与"协程" |

把链条连起来看：

```text
yield                  → 能暂停
yield + send           → 能接收 → 双向通信
yield from             → 能委托 → 协程可以嵌套（await 的前身）
async/await            → 语法独立、事件循环接管调度
```

`await` 干的事和 `yield from` 在机制上高度同构：**挂起当前帧、把控制权交出去、等对方结束后拿回结果**。区别在调度者——`yield from` 由你手动驱动，`await` 由事件循环驱动；以及语义约束——原生协程不能被 `send` 随便塞值，`await` 只能等可等待对象。

这也解释了 chapter12 那篇协程文档里的结论：协程挂起时帧在堆上，和生成器完全同一套机制，只是协程对象多了 `cr_await`、`cr_running` 等字段来描述"我在等谁"。

---

## 十一、工程要点与常见坑

1. **只能消费一次。** 耗尽后再迭代得到空结果，且不报错：
   ```python
   g = (i for i in [1, 2])
   list(g)   # [1, 2]
   list(g)   # []  ← 静默为空，最容易埋 bug
   ```
   要复用就重新调用生成器函数（每次返回新对象），或显式 `list()` 缓存。

2. **没有 `len()`、不能索引。** `len(g)` → `TypeError`，`g[0]` → `not subscriptable`。惰性的代价：它不知道还剩多少。

3. **函数体在首次驱动时才执行**，包括其中的错误：
   ```python
   def g1():
       raise ValueError("函数体里的错误")
       yield
   obj = g1()      # 不报错
   next(obj)       # 此时才抛 ValueError
   ```
   所以"创建生成器"不能当作"校验通过"。

4. **延迟绑定：生成器只在迭代那一刻读外部状态。**
   ```python
   data = [1, 2, 3]
   g = (x * 10 for x in data)
   data.append(4)
   list(g)          # [10, 20, 30, 40] ← 读的是修改后的 data
   ```
   同理，闭包捕获循环变量会得到"最后一个值"（`[lambda: i for i in range(3)]` 全部返回 `2`）。需要快照就提前 `list()` 或绑定默认参数。

5. **资源型生成器要保证被关闭。** 靠 `finally` + `close()`，或直接用 `contextlib.closing`。别指望"反正会被 GC"——CPython 引用计数确实会兜底，但 PyPy 等实现不保证时机。

6. **`send` 前先 prime。** 自己写个包装函数（`next(g)` 一次再返回 `g`）最省事；如果你写的是"被驱动"的协程，就让驱动方（事件循环 / 调度器）负责预热。

7. **调试挂起态**：`g.gi_frame.f_locals` 能直接看到生成器停在哪儿、局部变量是什么，比打日志快。

### 11.1 两个真实的工程用法

**流式管道**（生成器串联，内存恒定）：

```python
def read_lines(path):
    with open(path, encoding="utf-8") as f:
        yield from f            # 逐行，永不整体载入

def only_errors(lines):
    for line in lines:
        if "ERROR" in line:
            yield line.strip()

for line in only_errors(read_lines("app.log")):
    ...
```

**用生成器写上下文管理器**（`contextmanager` 就是"把 `yield` 当分界线"）：

```python
from contextlib import contextmanager

@contextmanager
def cm():
    print("__enter__ 部分")
    try:
        yield "资源"
    finally:
        print("__exit__ 部分")

with cm() as r:
    print("with 内部:", r)
```

实测输出三段依次是 `__enter__ 部分` → `with 内部: 资源` → `__exit__ 部分`。`yield` 之前 = `__enter__`，`yield` 之后 = `__exit__`，`throw` = 异常进 `__exit__`——**上下文管理器协议被生成器的暂停/恢复完美映射**。

FastAPI 的 `yield` 依赖（chapter09 提过的 `get_db`）也是同一套逻辑：`yield` 前建会话，`yield` 后关会话，请求期间挂起。

---

## 十二、总结

### 一张表记住全部

| 问题 | 答案 |
|---|---|
| 调用生成器函数时执行了什么 | 只执行 `RETURN_GENERATOR`，返回对象，函数体不动 |
| `yield` 是语句还是表达式 | 表达式，有值，值是下次 `send()` 送进来的 |
| 暂停时状态存哪 | 堆上的帧对象：`f_lasti`（执行位置）+ `f_locals`（局部变量） |
| 怎么恢复 | 拿 `f_lasti` 重新进入帧，`send` 用返回值恢复、`throw` 用异常恢复 |
| `send()` 返回什么 | 下一个 `yield` 的产出，**不是** `return` 值 |
| `return` 的值去哪了 | `StopIteration.value`，`yield from` 能接住，`for` 会丢掉 |
| 有几种结束方式 | 耗尽 / `close()` / GC，都会跑 `finally`；未启动就 close 则不跑 |
| `yield from` 和 `for + yield` 差什么 | 多透传 `send`、`throw`、`return` 三路，并自动启动/收尾 |
| 和协程什么关系 | 生成器 + `send` = 协程雏形；`yield from` ≈ `await` 的机制前身 |

### 一句话记忆

> **生成器 = 一个躺在堆上的帧 + 一个 `f_lasti` 指针 + 一套"交出/收回"的协议。**
> `next` 是"继续跑"，`send` 是"继续跑并捎句话进去"，`throw` 是"继续跑但先挨一记异常"，`close` 是"别跑了，收尾"。
> 把这四件事想通，协程就只剩"谁来驱动"这一个新问题了。

## 十三、呼应章节

- chapter05 `Python生成器详解.md`：用途与 Java 对照（本文不重复，只补运行逻辑）。
- chapter09 `02Python生成器函数与栈帧详解.md`：为什么帧能在堆上独立存活——本文第三节的 `f_lasti`/`f_locals` 是那篇的运行时证据。
- chapter12 `Python协程详解及与Go、Java对比.md`：协程的帧存储、内存开销与三语言对比；本文第十节是它的前传。
- chapter08 `Python描述符协议详解.md`：`contextmanager` 背后的 `_GeneratorContextManager` 就是描述符 + 生成器的组合。
