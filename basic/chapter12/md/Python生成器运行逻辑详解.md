# Python 生成器的运行逻辑

> 存放位置：`basic\chapter12\md\Python生成器运行逻辑详解.md`
> 验证环境：`D:\python\fastapi_test\.venv`（Python 3.13.9），本文所有代码与输出均实测
> 分工：chapter05 讲**用途与 Java 对照**，chapter09 讲**帧为什么能在堆上**；本文只讲**被驱动时内部怎么跑**
> 本版说明：按"结论 → 机制 → 边界 → 对比 → 误解"重排优先级。逐条字节码解读、PEP 演进史、工程用法降为附录——它们是需要时回查的证据，不是理解主线。

## 一句话结论

**生成器是一个挂在堆上、可暂停的栈帧：`yield` 交出值并冻住，被驱动时按 `f_lasti` 续跑。**

---

## 一、结论层：三个反直觉的事实

| 事实 | 依据 | 常被误认为 |
|---|---|---|
| 调用生成器函数**不执行函数体** | 首条字节码 `RETURN_GENERATOR`，直接返回对象 | "至少会跑一遍" |
| `yield` 是**表达式**，有值 | 值是下次 `send()` 送进来的 | "`yield` 就是 `return`" |
| `next` / `send` / `throw` / `close` 是**同一个操作** | 都以不同方式恢复同一帧 | "四套独立 API" |

这三条都不是"事实陈述"，而是三个判断。下面所有机制，都是对它们的展开。

---

## 二、机制层：只有一条因果链

```text
帧分配在堆上  →  暂停时没人销毁它  →  可以带着 f_lasti + f_locals 等下次被驱动
```

CPython 的栈帧是普通对象，不受调用栈后进先出约束（详见 chapter09）。生成器"能暂停"不是什么特殊能力，只是**没有强制销毁这个帧**。

三个推论全部由此推出。

### 2.1 能恢复：`f_lasti` 记住下一条指令

```python
import inspect

def trace():
    a = 1
    yield a
    b = a + 1
    yield b
    c = b * 2
    yield c

g = trace()
print(inspect.getgeneratorstate(g))   # GEN_CREATED
next(g)   # value=1, f_lasti=14, f_locals={'a': 1}
next(g)   # value=2, f_lasti=32, f_locals={'a': 1, 'b': 2}
next(g)   # value=4, f_lasti=50, f_locals={'a': 1, 'b': 2, 'c': 4}
next(g)   # StopIteration, gi_frame = None
```

`f_lasti` 递增、`f_locals` 累积。**"保存状态"不是把变量拷贝走，而是它们本来就在这个堆上的帧里，没人清掉。**

四个状态单向流转：

| 状态 | `gi_frame` | 能否驱动 |
|---|---|---|
| `GEN_CREATED` | 有（`f_lasti=2`，指向第一条 `RESUME`；`f_locals={}`） | 只能 `next()` / `send(None)` |
| `GEN_RUNNING` | 有 | 不能重入，否则 `ValueError` |
| `GEN_SUSPENDED` | 有（保存 `f_lasti` / `f_locals`） | 可 `next`/`send`/`throw`/`close` |
| `GEN_CLOSED` | **`None`** | 只会得到 `StopIteration` |

`GEN_CLOSED` 时 `gi_frame` 变 `None` 不是"清空内容"，而是**帧被释放**——所以关闭后物理上无法恢复，不是"重置了状态"。

### 2.2 能双向：`yield` 先交出，再收回

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

实测输出顺序是 `[A]` → `产出值` → `[B]`。也就是说 `received = yield "产出值"` 分两次执行：

1. 第一次驱动：交出值并暂停，**赋值还没发生**；
2. 第二次驱动：`yield` 表达式此刻才求值完毕，结果是送进来的值。

由此得到 `send()` 的语义——**它返回的是"下一个 `yield` 的产出"，不是函数返回值**：

| 你以为 | 实际 |
|---|---|
| `send(x)` 返回 `return` 的值 | 返回下一个 `yield` 产出的值 |
| 函数 `return` 的值直接拿到 | 藏在 `StopIteration.value` 里 |

因为 `send()` 能正常返回就说明"还没结束"；一旦结束，没有"下一个产出"可返回，只能靠异常同时表达"结束了"和"结束值是什么"。

`throw` 是同一机制的另一条恢复路径：它不送值，而是**在挂起点抛异常**。所以 `send` 与 `throw` 正好对应函数调用的两条出路——正常返回、异常上抛。

### 2.3 `yield from`：一行委托，四件事

先说结论：`yield from sub()` 这一行，等价于**手写 19 行**（实测，且还不含 `throw` 透传）。所谓"透传"不是玄学，是有四件具体的事被自动做掉了。

#### 一次完整交互

```python
def sub():
    print("  [sub] 启动")
    x = yield "S1"
    print(f"  [sub] yield 表达式收到 {x!r}")
    y = yield "S2"
    print(f"  [sub] yield 表达式收到 {y!r}")
    return "S-ret"

def outer():
    print("  [outer] 进入，开始委托")
    r = yield from sub()
    print(f"  [outer] yield from 表达式得到 {r!r}")
    return r.upper()
```

驱动三次，看每一步实际执行到哪：

| 你的动作 | 实际执行到哪 | 返回给你 |
|---|---|---|
| `d.send(None)` | outer 进入 → 委托 → **sub 启动** → 产出 `"S1"` | `"S1"` |
| `d.send("A")` | **sub** 的 `x = yield "S1"` 求值 → 产出 `"S2"` | `"S2"` |
| `d.send("B")` | sub 收到后 `return` → `yield from` 表达式得 `"S-ret"` → outer `return` | `StopIteration("S-RET")` |

实测输出（原文照录）：

```text
>>> d.send(None)
  [outer] 进入，开始委托
  [sub] 启动
    返回: 'S1'
>>> d.send('A')
  [sub] yield 表达式收到 'A'
    返回: 'S2'
>>> d.send('B')
  [sub] yield 表达式收到 'B'
  [outer] yield from 表达式得到 'S-ret'
    StopIteration.value = 'S-RET'
```

**盯住第二次驱动：`send("A")` 的值没有经过 `outer` 的任何一行业务代码，直接落进了 `sub` 的 `yield` 表达式。** 这就是"透传"的字面含义——`outer` 只是导管，不做中转处理。

#### 四件事逐项对照

| # | 事件 | 发起方 | 落点 | 手写时你要做什么 |
|---|---|---|---|---|
| 1 | **产出** | `sub` 的 `yield` | 直接到你的调用者 | `for v in sub(): yield v` |
| 2 | **送值** | 你的 `send(v)` | `sub` 的 `yield` 表达式 | 手动转交（`for` 做不到） |
| 3 | **异常** | 你的 `throw(e)` | `sub` 内部抛出 | 手动 `gen.throw(e)` |
| 4 | **收尾** | `sub` 的 `return r` | 成为 `yield from` 表达式的值 | `try/except StopIteration` 取 `e.value` |

第 3、4 路换一组子生成器来验证（外层都只是 `yield from` 的包装）：

```python
def sub_t():                       # 内部捕获异常，然后继续产出
    try:
        yield "T1"
    except ValueError as e:
        print(f"  [sub_t] 捕获 {e!r}")
        yield "T-recovered"
    return "T-ret"

def sub_c():                       # 用 finally 观察它是否被 close
    try:
        yield "C1"
    finally:
        print("  [sub_c] finally 清理执行")
```

实测：

```text
>>> d.send(None)
    返回: 'T1'
>>> d.throw(ValueError('boom'))
  [sub_t] 捕获 ValueError('boom')
    返回: 'T-recovered'
    StopIteration.value = 'T-RET'
```

`throw` 的异常是在**子生成器内部**被捕获的，`outer_t` 完全不知情；子生成器接住后继续产出，最后正常 `return`，返回值再一路透传到最外层——第 3 路和第 4 路在这里叠在一起。

close 透传：`d.close()` 之后 `outer_c` 状态为 `GEN_CLOSED`，且子生成器的 `finally` 被执行：

```text
  [sub_c] finally 清理执行
  outer_c 状态: GEN_CLOSED
```

#### 为什么 `for` 替不了它

```python
def manual():
    for v in sub():
        yield v

m = manual()
next(m)          # 'S1'
m.send(99)       # 返回 'S2'，但 sub 里的 x 收到的是 None
```

`send(99)` **不报错**：值落到外层 `yield v` 的恢复点，被 `POP_TOP` 丢掉。静默丢弃比报错危险——协程看起来在跑，上级指令却永远收不到。

`for` 只做了第 1 件事（产出），第 2、3、4 路全断。

#### 手写到底有多长

即使砍掉 `throw` 透传，也要 19 行：

```python
def delegate(gen):                            # 不含 throw 透传
    gen = iter(gen)
    try:
        value = next(gen)                     # 1 启动，拿第一个产出
    except StopIteration as e:
        return e.value                        # 4 一启动就结束了
    while True:
        try:
            sent = yield value                # 1 产出，2 接收 send
        except GeneratorExit:
            gen.close()                       # 3 close 透传
            raise
        try:
            if sent is None:
                value = next(gen)             # 2 无值则推进
            else:
                value = gen.send(sent)        # 2 有值则送进去
        except StopIteration as e:
            return e.value                    # 4 收尾，取 return 值
```

补上 `throw` 透传、以及对"没有 `throw`/`close` 的普通迭代器"的兼容，才是完整版——26 行：

```python
def delegate(gen):
    gen = iter(gen)
    try:
        value = next(gen)                     # 启动子生成器
    except StopIteration as e:
        return e.value                        # 一启动就结束
    while True:
        try:
            sent = yield value                # 产出，并接收 send
        except GeneratorExit:
            close = getattr(gen, "close", None)
            if close is not None:
                close()                       # close 透传
            raise
        except BaseException as exc:
            if not hasattr(gen, "throw"):
                raise                         # 子迭代器不支持 throw
            try:
                value = gen.throw(exc)        # throw 透传
            except StopIteration as e:
                return e.value
        else:
            try:
                value = next(gen) if sent is None else gen.send(sent)
            except StopIteration as e:
                return e.value                # 收尾，返回子生成器 return 值
```

六条路径实测（前四条外层写作 `r = yield from delegate(sub())`，后两条直接驱动 `delegate` 本身）：

| 用例 | 动作 | 实测结果 |
|---|---|---|
| send 透传 | `send("A")` | 子生成器 `x` 收到 `"A"`，返回 `"S2"` |
| throw 透传 | `throw(ValueError("boom"))` | 子生成器内部捕获，返回 `"T-recovered"` |
| close 透传 | `close()` | 子生成器 `finally` 执行；内外均 `GEN_CLOSED` |
| return 收尾 | 子生成器 `return "S-ret"` | 外层 `StopIteration("S-RET")` |
| 一启动就结束 | 第一句就 `return` | `StopIteration("empty-ret")` |
| 委托普通可迭代对象 | `delegate([1, 2, 3])` | `[1, 2, 3]`；对它 `throw` 会原样冒泡 |

两处实现细节值得注意：

- 用 `except BaseException as exc` 接住所有异常再 `gen.throw(exc)`。这里必须用**单参数**形式——Python 3.12 起 `throw(type, value, tb)` 三参数写法已弃用（PEP 380 原版展开里那个 `_x = sys.exc_info()` 就是旧式写法的遗留）。
- `getattr(gen, "close", None)` / `hasattr(gen, "throw")` 不是多余的防御：委托对象可能只是列表、字符串，它们没有 `throw` / `close`。这正是 `yield from` 能接受任意可迭代对象的原因。

#### 与 PEP 380 官方展开的变量对照

PEP 380 附录 A 给的是同一段逻辑，只是用了 `_i` / `_y` / `_r` / `_s` / `_e` 这套下划线命名（避免与用户变量冲突）：

| 官方变量 | 含义 | 本文写法 |
|---|---|---|
| `_i` | 子生成器（同时也是迭代器） | `gen` |
| `_y` | 子生成器产出的值 | `value` |
| `_r` | `yield from` 表达式最终的值 | `return e.value` 交出去的东西 |
| `_s` | 调用方 `send()` 送入的值 | `sent` |
| `_e` | 异常对象 | `e` / `exc` |

官方版比本文多两层结构：外层用 `try / except StopIteration / else` 三分支包住（本文改成"先 `next`，失败就 `return`"）；`throw` 分支里走 `_x = sys.exc_info()` 再 `_m(*_x)`——那是 3.12 已弃用的三参数写法，本文用单参数 `gen.throw(exc)`。

**看懂官方展开的方法：把 `_i` 读成"被委托的那个生成器"，然后逐行追问"这行在替谁做事"。答案只会落在那四件事里。**

`yield from` 把这 26 行折成 1 行，代价是**行为不再显式可见**——所以你才需要知道它暗中做了这四件事。

#### 边界

| 能 | 不能 |
|---|---|
| 委托任意可迭代对象（`yield from [1, 2]`、`yield from "ab"`，`GET_YIELD_FROM_ITER` 会先 `iter()`） | 聚合产出：它是逐条转发，不是 `list()` |
| 接住子生成器的 `return` 值 | 让 `for` 也拿到 `return` 值：`for` 只能拿到产出的值，`return` 值仅在 `StopIteration.value` 里 |

#### 证据：它不是语法糖

解释器会维护 `gi_yieldfrom` 指向子生成器：

```python
d = outer()
next(d)
d.gi_yieldfrom     # <generator object sub at 0x...>   ← 手写 for 委托时为 None
```

运行时能区分两种写法——如果是纯语法糖，这个字段不会是 `None`。

---

## 三、四个驱动入口，一个恢复机制

| 入口 | 等价于 | 恢复方式 |
|---|---|---|
| `next(g)` / `for` | `g.send(None)` | 让挂起的 `yield` 求值为 `None` |
| `g.send(v)` | — | 让挂起的 `yield` 求值为 `v` |
| `g.throw(e)` | — | **在挂起点抛出异常** |
| `g.close()` | `g.throw(GeneratorExit)` | 在挂起点抛 `GeneratorExit` |

```text
              next()/send(None)              next()/send(v)
GEN_CREATED ──────────────────► GEN_SUSPENDED ──────────────► GEN_SUSPENDED
     │                                │                              │
     │ close()                        │ throw(e)                     │ 函数体跑完
     ▼                                ▼                              ▼
GEN_CLOSED ◄────────────────── 异常冒出或再次挂起                 GEN_CLOSED
```

三个收尾细节，都不是常识能猜到的：

| 情况 | 行为 | `finally` 是否执行 |
|---|---|---|
| 自然耗尽 | 抛 `StopIteration(value)` | 执行 |
| `close()` / GC 回收 | 挂起点注入 `GeneratorExit` | 执行 |
| 未启动就 `close()` | 直接标记关闭 | **不执行**（函数体从未进入） |
| 未启动就 `throw()` | 在**调用点**直接抛出 | 不执行 |

`close()` 时若生成器再 `yield`，违反协议 → `RuntimeError: generator ignored GeneratorExit`。清理代码只放 `finally`，不要在 `except GeneratorExit` 里产出值。

---

## 四、边界：三条失效线

| 边界 | 表现 | 实测（10⁶ 全量消费） |
|---|---|---|
| **全量消费不更快** | 每元素一次 `RESUME`/`YIELD_VALUE` | `sum(genexpr)` 44.61ms vs `sum(range)` 15.81ms |
| **只能消费一次** | 耗尽后再迭代**静默返回空**，不报错 | `list(g)` → `[1,2]`，再 `list(g)` → `[]` |
| **不是协程** | 缺调度者与 `__await__` | 差的是"谁来驱动"，不是暂停能力 |

它赢的场景只有一个条件：**你会短路，或数据装不进内存。**

| 写法（只取前 10 个） | 耗时 | 内存 |
|---|---|---|
| `islice(expensive(), 10)` | **19.0 μs** | 生成器对象 192 字节 |
| `[i*i for i in range(10**7)][:10]` | 919.9 ms | 列表装下 1000 万个 int（数百 MB） |

四个数量级。所以判断标准不是"生成器更快吗"，而是"我会不会只消费一部分"。

---

## 五、对比表：三个最易混淆的东西

| 维度 | 生成器 | 迭代器（手写类） | 原生协程 |
|---|---|---|---|
| 暂停点 | `yield`（自动） | 无，靠 `__next__` 返回 | `await`（自动） |
| 状态保存 | 帧自动保留 | 手动写字段 | 帧自动保留 |
| 谁驱动 | 你 / `for` | 你 / `for` | 事件循环 |
| 能接收外部值 | 能（`send`） | 不能 | 不能（`send` 受限） |
| 典型内存 | 192 字节/个 | 视字段而定 | 1~2 KB/个 |

三者共用同一套"帧挂起/恢复"机制，差别在**语义约束**与**调度者**。

---

## 六、常见误解

1. **原以为** `send()` 返回函数 `return` 值，**实际**返回下一个 `yield` 的产出；`return` 值只在 `StopIteration.value` 里。
2. **原以为** `for + yield` 等价 `yield from`，**实际** `send` 的值被静默丢弃，子生成器收到 `None`——比报错更难发现。
3. **原以为** 生成器总比列表快，**实际**全量消费时慢近 3 倍（44.61 vs 15.81ms），优势只在短路与内存。

---

## 七、自检问题

1. 如果把 `yield x` 改成 `yield x; x = None`，两次驱动之间 `f_locals` 会多出什么？为什么？
2. 为什么 `close()` 之后再 `next()` 只得到 `StopIteration`，而不是"从头重跑"？

答对第 2 题，说明你抓住的是"帧被释放"，而不是"状态被重置"——这是本文唯一的主线。

---

## 八、总结

| 问题 | 答案 |
|---|---|
| 调用时执行了什么 | 只有 `RETURN_GENERATOR`，函数体不动 |
| `yield` 是语句还是表达式 | 表达式，值是下次 `send()` 送入的 |
| 暂停时状态存哪 | 堆上帧：`f_lasti` + `f_locals` |
| 怎么恢复 | 按 `f_lasti` 重新进帧；`send` 用返回值、`throw` 用异常 |
| 怎么结束 | 耗尽 / `close` / GC，都跑 `finally`；未启动就 close 不跑 |

> **生成器 = 堆上的帧 + `f_lasti` 指针 + 一套"交出/收回"协议。**
> `next` 继续跑，`send` 继续跑并捎句话，`throw` 继续跑但先挨一记异常，`close` 别跑了收尾。

---

## 附录 A：字节码证据

`dis.dis(simple)` 的关键部分（Python 3.13）：

```text
  RETURN_GENERATOR
  POP_TOP
L1: RESUME 0
  ... 计算 ...
  YIELD_VALUE 0
  RESUME 5
  POP_TOP
  RETURN_CONST 0 (None)
L2: CALL_INTRINSIC_1 3 (INTRINSIC_STOPITERATION_ERROR)
  RERAISE 1
```

| 指令 | 对应结论 |
|---|---|
| `RETURN_GENERATOR` | 调用即返回对象，函数体不执行 |
| `YIELD_VALUE` / `RESUME` | 永远成对：一对就是一个暂停点 |
| `POP_TOP` | 丢弃送进来但没人接收的值 |
| `INTRINSIC_STOPITERATION_ERROR` | PEP 479 的落地位置 |

PEP 479 的具体行为：生成器内部漏出的 `StopIteration` 一律转成 `RuntimeError`（原异常挂在 `__cause__`）。原因是 `StopIteration` 本身就是"迭代结束"的信号，若从生成器漏出，外层 `for` 会误以为正常结束，而实际是半路出错。正确写法是显式捕获后 `return`。

补充：`co_flags` 实测 `0x23`（含 `CO_GENERATOR` 位），普通函数为 `0x3`。

## 附录 B：PEP 演进

| PEP | 提出 / 落地 | 加了什么 | 意义 |
|---|---|---|---|
| 255 | 2001 / 2.2 | `yield` | 能暂停 |
| 342 | 2005 / 2.5 | `send` / `throw` / `close` | 能接收 → 双向通道 |
| 380 | 2009 / 3.3 | `yield from` | 能委托 → 可分层组合 |
| 3156 | 2012 / 3.4 | `asyncio` | 事件循环接管调度 |
| 492 | 2015 / 3.5 | `async` / `await` | 语法层面区分生成器与协程 |

`await` 与 `yield from` 机制同构，差在调度者与语义约束。协程的帧存储与内存开销见 chapter12 `Python协程详解及与Go、Java对比.md`。

## 附录 C：工程用法

```python
# 流式管道：内存恒定
def read_lines(path):
    with open(path, encoding="utf-8") as f:
        yield from f

def only_errors(lines):
    for line in lines:
        if "ERROR" in line:
            yield line.strip()

# 生成器写上下文管理器：yield 前是 __enter__，yield 后是 __exit__
from contextlib import contextmanager

@contextmanager
def cm():
    print("__enter__")
    try:
        yield "资源"
    finally:
        print("__exit__")
```

FastAPI 的 `yield` 依赖（chapter09 的 `get_db`）同理：`yield` 前建会话，`yield` 后关会话。

## 九、呼应章节

- chapter05 `Python生成器详解.md`：用途、与 Java 的对照
- chapter09 `02Python生成器函数与栈帧详解.md`：帧为何能在堆上独立存活
- chapter12 `Python协程详解及与Go、Java对比.md`：协程的帧存储、内存与三语言差异
- chapter08 `Python描述符协议详解.md`：`contextmanager` 背后的描述符 + 生成器组合
