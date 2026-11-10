# Python 与 Java 的垃圾回收机制详解与对比

> 存放位置：`basic\chapter07\md\Python与Java垃圾回收机制对比.md`
> 前置知识：对象生命周期、内存分配、引用概念（`is`/`==` 见同章另一文档）
> 配套验证：**Python 侧全部在本机 `.venv`（Python 3.13）实测**；**Java 侧基于 HotSpot JVM（JDK 8）官方规范与源码描述，本机仅 JRE 无 javac，未能编译实测**

## 一句话结论

两者都自动回收堆内存，但**机制根本不同**：

- **Python：引用计数为主 + 分代收集兜底**——对象被引用归零的瞬间确定性回收；引用计数解决不了的循环引用，交给分代 GC。
- **Java：可达性分析 + 分代收集**——从 GC Roots 出发标记不可达对象，天然处理循环引用；靠分代与多种收集器控制停顿。

---

## 1. Python 的垃圾回收

### 1.1 引用计数（主力，即时确定性）

每个对象头部有 `ob_refcnt` 计数：

- **增加**：变量引用、入列表/字典/set、函数参数传递、属性赋值。
- **减少**：`del`、变量被重新赋值、出容器、函数返回。
- **归零 → 立即回收**：内存马上释放，`__del__` 立刻执行——这是 Python 与 Java 最大的气质差异（**确定性**）。

实测（Python 3.13）：

```
创建后 refcount: 1
入列表后:        2
出列表后:        1
del t 前（对象仍活着）
  → Track.__del__ 被调用        ← del 的瞬间就执行，不等"GC 有空"
del t 后（__del__ 已在上一步执行）
```

```python
import sys
class Obj: pass
o = Obj()
print(sys.getrefcount(o) - 1)   # 1
lst = [o]
print(sys.getrefcount(o) - 1)   # 2
del lst
print(sys.getrefcount(o) - 1)   # 1
```

### 1.2 引用计数的死穴：循环引用

`a.peer = b; b.peer = a` —— 互相持有，引用计数永不归零，**引用计数永远收不掉**。解法是分代循环引用收集器。

### 1.3 分代循环引用收集（兜底）

- **三代**：0 代（新对象）、1 代、2 代（老对象）。
- **触发**：0 代待收集对象数超过阈值时触发，存活对象晋升到 1 代；1/2 代阈值（10, 10）控制是否连带收集老对象。
- **阈值实测**（3.13）：`gc.get_threshold()` → `(2000, 10, 10)`。
- **手动干预**：`gc.collect()` 强制收集；`gc.disable()` 关掉自动收集（危险）。

实测循环引用：

```
gc.disable 后循环引用是否泄漏: True   ← 没有 GC 兜底，两个对象泄漏
gc.collect 手动收集后: True            ← 分代 GC 把循环引用收掉了
```

```python
import gc, weakref
class Node:
    def __init__(self): self.peer = None

n1, n2 = Node(), Node()
n1.peer, n2.peer = n2, n1     # 循环引用
w1 = weakref.ref(n1)
gc.disable()
del n1, n2
print(w1() is not None)       # True ← 泄漏
gc.collect()
print(w1() is None)           # True ← 被回收
```

### 1.4 弱引用（weakref）

`weakref.ref(obj)` 不增加引用计数——对象回收后弱引用自动变 None。用于缓存、回调等"想引用但不想阻止回收"的场景：

```python
import weakref
w = weakref.ref(obj)
print(w() is None)   # obj 存活时为对象，回收后为 None
```

### 1.5 Python GC 的坑

1. **带 `__del__` 的循环引用**：3.4 之前无法确定销毁顺序，这类对象直接不回收（进 `gc.garbage`）；3.4+ 有 `PEP 442` 才安全处理——所以**尽量别在 `__del__` 里依赖全局状态**。
2. **`gc.disable()` 很危险**：一旦关闭，循环引用全部泄漏（实测演示）。
3. **引用计数有额外开销**：每次赋值/入容器都要增减计数，纯 Python 对象比 JVM 对象"贵"一点。
4. **`del` 只是减计数**：多别名时 `del x` 不回收，所有引用都没了才回收。

---

## 2. Java（HotSpot JVM）的垃圾回收

### 2.1 可达性分析（核心算法）

- 从 **GC Roots**（栈帧局部变量、静态字段、JNI 引用、活跃线程等）出发做引用遍历；**不可达的对象就是垃圾**。
- 不依赖引用计数 → **循环引用天然被正确回收**（互相引用但无根可达，一样是垃圾）。
- 标记-清除 / 标记-整理 / 复制三类基础算法，各收集器组合使用。

### 2.2 分代堆结构（HotSpot 默认）

```
                    Heap
┌────────────────────────────────────────────────┐
│  Young Gen（新生代）                            │
│  ┌────────┬──────┬──────┐                      │
│  │  Eden  │ S0   │ S1   │  复制算法（存活复制）  │
│  └────────┴──────┴──────┘   → Minor GC         │
│  Old Gen（老年代）                               │
│  标记-清除 / 标记-整理 → Major/Full GC           │
└────────────────────────────────────────────────┘
Metaspace（元空间，JDK 8 起替代永久代：类元数据）
```

- **新生代**（约占 1/3）：Eden + 两个 Survivor（S0/S1），对象先放 Eden；Minor GC 时存活对象复制到 Survivor，熬过多次 GC 后晋升老年代（**复制算法**：快、无碎片）。
- **老年代**：大对象与长寿对象；Major/Full GC 用**标记-清除/标记-整理**（慢、有停顿）。
- **Metaspace**：类元数据，默认无上限（受本地内存约束），不在堆内。

### 2.3 收集器演进（关键点）

| 收集器 | 年代 | 特点 | 状态 |
|---|---|---|---|
| Serial | 单线程 | 简单，适合小堆/客户端 | 老牌 |
| Parallel | 多线程 | **吞吐优先**，Java 8 默认 | 经典 |
| CMS | 并发 | 低停顿，但碎片化严重 | JDK 9 弃用，14 移除 |
| **G1** | 区域化 | **可预测停顿**，把堆分成 Region，JDK 9+ 默认 | 主流 |
| **ZGC** | 全并发 | **毫秒级停顿**（染色指针），可伸缩至 TB 级堆 | JDK 15+ 稳定 |
| Shenandoah | 全并发 | 停顿与堆大小无关 | JDK 12+ |

- G1 的思路：把堆切成大量小 Region，增量式回收，通过停顿预测模型尽量满足 `-XX:MaxGCPauseMillis` 目标。
- ZGC：GC 线程与应用线程几乎完全并发，停顿与堆大小无关（适合超大堆、低延迟服务）。

### 2.4 触发与干预

- **自动**：堆使用率超过阈值、晋升失败（promotion failure）、元空间超限等触发 Minor/Full GC。
- **`System.gc()` 只是"建议"**：JVM 可能忽略；`-XX:+ExplicitGCInvokesConcurrent` 可让它变成并发收集。
- **调优参数**（示例）：`-Xmx4g`（堆上限）、`-Xms4g`（初始）、`-XX:MaxGCPauseMillis=100`（G1 停顿目标）、`-XX:+UseZGC`。

### 2.5 Java GC 的坑

1. **停顿（STW）**：即使 G1/ZGC 也有短暂停顿（ZGC 目标 <10ms）；日志里关注 `GC pause` 事件。
2. **`System.gc()` 不保证执行**：依赖 JVM 决策，别用它做业务逻辑。
3. **大对象直接进老年代**：`-XX:PretenureSizeThreshold` 可调，避免大对象反复复制。
4. **泄漏不是 GC 的事**：静态集合持有对象引用、监听器未注销等"可达泄漏"GC 永远收不掉。

---

## 3. 全面对比表

| 维度 | Python | Java（HotSpot） |
|---|---|---|
| 核心算法 | **引用计数** + 分代循环引用收集 | **可达性分析** + 分代收集 |
| 循环引用 | 引用计数收不掉，需分代 GC 兜底 | 天然正确（不可达即垃圾） |
| 回收时机 | **确定性**：计数归零立即回收 | **不确定**：GC 自行触发（`System.gc()` 仅建议） |
| `__del__` / `finalize` | `__del__` 在归零瞬间执行 | `finalize` 已弃用（JDK 9+ deprecated），用 `try-with-resources`/`Cleaner` |
| 暂停（STW） | 引用计数无 STW；分代 GC 有极短暂停 | 有 STW；G1 可预测、ZGC 毫秒级 |
| 每对象内存开销 | `ob_refcnt` 字段 | 对象头（mark word + klass） |
| 手动干预 | `gc.collect()` **真的执行** | `System.gc()` **只是建议** |
| 分代 | 0/1/2 代（阈值 2000, 10, 10 实测） | Young（Eden/S0/S1）+ Old + Metaspace |
| 弱引用 | `weakref.ref` | `WeakReference` / `WeakHashMap` |
| 线程模型 | GIL 下原子，无并发 GC 问题 | 多线程并发回收（并/串行收集器可选） |

## 4. 一句话记忆

> **Python：计数归零立即回收（确定性），循环引用靠分代兜底（`gc` 模块）；Java：GC Roots 可达性分析（循环引用天然没事），分代 + G1/ZGC 控制停顿**。一个确定性到"`del` 就执行 `__del__`"，一个讲究"停顿可预测"——同一目标（自动回收垃圾），两条截然不同的工程路线。

## 5. 呼应章节

- chapter07 `is与等于号区别及intern机制.md`：`id()` 与对象生命周期直接相关——引用计数归零后 `id` 可能被复用，`weakref` 与 intern 单例都依赖"对象是否还活着"。
- chapter06 `dict与set实现原理及Java对照.md`：dict 键的 hash/`==` 查找在对象被 GC 回收后失效，弱引用键字典（`weakref.WeakKeyDictionary`）是正确姿势。
- chapter05 序列容器：`deque`/`list` 的元素引用同样参与引用计数（入容器 +1、出容器 -1）。
