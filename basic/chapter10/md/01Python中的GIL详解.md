# Python 中的 GIL 详解

## 一个常见的误解

"Python 没有多线程"——这是错的。Python 有**真正的多线程**，`threading.Thread` 创建的就是货真价实的操作系统线程。

真正的问题是：在 CPython 中，多个线程**不能并行执行 Python 字节码**。罪魁祸首就是 GIL。

## GIL 是什么

GIL（Global Interpreter Lock，全局解释器锁）是 CPython 解释器内部的一把互斥锁：

> 同一时刻，整个进程内只允许一个线程执行 Python 字节码。其他线程即使抢到了 CPU，也必须先拿到 GIL 才能运行，拿不到就只能等待。

## 为什么要有 GIL

根本原因：CPython 的内存管理采用**引用计数**（reference counting）。每个对象内部记录"有多少变量引用着我"，减到 0 就销毁。多个线程同时修改同一对象的引用计数会产生竞态条件，导致内存泄漏或对象被提前释放。

要保证线程安全，有两条路：

| 方案 | 代价 |
|---|---|
| 1. 给每个对象加细粒度锁 | 实现极复杂；单线程性能大幅下降 |
| 2. 加一把全局大锁，一次只放一个线程进解释器 | 实现简单；单线程反而更快 |

1990 年代 CPython 的设计者选择了方案 2，这就是 GIL——**用牺牲多线程并行性，换来单线程高性能和实现简单**。

## GIL 的实际影响

GIL 杀死的是**并行（parallelism）**，不是**并发（concurrency）**。分两种情况看：

- **CPU 密集型任务**（大量计算）：开 4 个线程，仍然是轮流拿 GIL、只有一个核在算，总耗时不变。线程切换和锁竞争还有额外开销，甚至可能比单线程**更慢**。
- **I/O 密集型任务**（网络请求、读写文件、`sleep`）：线程在阻塞等 I/O 时会**主动释放 GIL**，让其他线程运行。所以爬虫、批量请求这类场景，多线程依然有效。

一句话总结：

> Python 不是"没有多线程"，而是 CPython 的多线程因为 GIL 只能并发、不能并行。**I/O 密集用多线程或 asyncio；CPU 密集用多进程。**

## 快速验证

```python
import time
from threading import Thread

def cpu_task():
    n = 0
    for i in range(50_000_000):
        n += i

# 单线程
start = time.perf_counter()
cpu_task(); cpu_task()
print(f"单线程: {time.perf_counter() - start:.2f}s")

# 双线程（CPU 密集，GIL 导致无法加速）
start = time.perf_counter()
t1, t2 = Thread(target=cpu_task), Thread(target=cpu_task)
t1.start(); t2.start()
t1.join(); t2.join()
print(f"双线程: {time.perf_counter() - start:.2f}s")
```

典型输出：双线程耗时和单线程几乎一样（甚至更久），因为两个线程在抢同一把 GIL。把 `cpu_task` 换成 `time.sleep` 模拟 I/O，双线程就几乎是单线程的一半耗时。

## 如何绕开 GIL

| 方案 | 适用场景 |
|---|---|
| `multiprocessing` / `ProcessPoolExecutor` | CPU 密集型——每个进程有独立解释器和 GIL，真正利用多核 |
| `asyncio` | 高并发 I/O——单线程内协程切换，开销远小于线程 |
| C 扩展（如 NumPy） | 底层计算耗时会释放 GIL，内部可自由并行 |
| Python 3.13+ free-threading 构建 | PEP 703 的无 GIL 版本，已可官方使用（非默认），是未来移除 GIL 的过渡方案 |

## 和 FastAPI 的关系

- FastAPI 高并发的核心是 **asyncio**：`async def` 路由在单线程内用协程并发处理大量 I/O，完全绕开了多线程开销。
- 普通 `def` 路由会被扔进**线程池**运行——适合 I/O 操作，但别在里面放重计算。
- 真正吃 CPU 的计算，要么用 `ProcessPoolExecutor` 跑在独立进程里，要么交给外部服务（如消息队列 + worker）。

## 面试要点

1. GIL 是什么？为什么存在？（引用计数不是线程安全的，全局锁换简单和单线程性能）
2. GIL 限制的是并行还是并发？（并行；I/O 期间会释放，所以 I/O 密集多线程仍有效）
3. CPU 密集和 I/O 密集分别怎么选？（多进程 / asyncio 或多线程）
4. 了解 free-threading（PEP 703）吗？（3.13+ 可选的无 GIL 构建）
