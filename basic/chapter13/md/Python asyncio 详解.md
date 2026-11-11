# Python asyncio 详解：事件循环、任务调度与方法地图

> 存放位置：`basic\chapter13\md\Python asyncio 详解.md`
> 验证环境：`D:\python\fastapi_test\.venv`（Python 3.13.9），本文所有代码与数字均实测
> 分工：chapter11 讲**同步/异步、阻塞/非阻塞的区分**（概念层）；chapter12 讲**协程的帧与挂起原理**（机制层）；本文讲 **asyncio 这个库怎么用、方法怎么选**（应用层）
> 前置：知道 `async def` 定义协程、`await` 会挂起，但不清楚事件循环在做什么

## 一句话结论

**asyncio 是"单线程事件循环 + 协程调度器"：协程在 `await` 处交出控制权，循环在 I/O 就绪时把它恢复——所以并发来自"等待时去干别的"，不是来自多线程。**

---

## 一、结论层：三个对象，一个循环

| 对象 | 是什么 | 谁创建 |
|---|---|---|
| 协程对象（coroutine） | `async def` 函数调用后的返回值，**只是一段可暂停的代码，还没开始跑** | 你调用函数时 |
| Task | 被**排进事件循环**的协程，带状态、可取消、可取名 | `create_task` / `TaskGroup` / `gather` |
| 事件循环（loop） | 调度器：维护就绪队列与 I/O 监听，决定"下一个跑谁" | `asyncio.run()` 内部创建 |

```python
import asyncio

async def work():
    await asyncio.sleep(0.1)
    return "done"

async def main():
    coro = work()                  # 协程对象，此刻没执行
    task = asyncio.create_task(coro)   # 交给循环，开始排队
    print(type(coro).__name__, "|", type(task).__name__)
    print(await task)              # 等它完成

asyncio.run(main())
```

关键区分：**协程是"值"，Task 才是"已排入调度的工作"**。`await coro` 能跑，是因为 await 会临时把它包装成 Task。

---

## 二、机制层：单线程为什么能并发

### 2.1 一次 `await` 发生了什么

```text
协程 A 执行到 await，遇到一个"还不能立刻给结果"的操作
  → A 挂起，把自己注册到该操作的完成回调上
  → 控制权交还事件循环
  → 循环从就绪队列里挑 B 开始跑
  → A 等待的 I/O 就绪，循环把 A 放回就绪队列
  → 下一轮，A 从 await 处恢复
```

整个过程只有**一个线程**，没有线程切换，也没有内核态参与。这就是 asyncio 开销远小于线程的原因：切换的只是一个帧的引用（见 chapter12 的堆上帧）。

### 2.2 协作式切换：只在 `await` 处切

这是 asyncio 最容易被忽略的约束：**协程不会被打断**。只要它不 `await`，事件循环就没有机会切走。

实测代价——在一个协程里写同步阻塞调用：

```python
import asyncio
import time

async def main():
    ticks = []

    async def ticker():               # 每 50ms 记录一次时间戳
        for _ in range(8):
            ticks.append(time.perf_counter())
            await asyncio.sleep(0.05)

    tk = asyncio.create_task(ticker())
    await asyncio.sleep(0.12)         # 先让 ticker 跑起来
    time.sleep(0.3)                   # 故意同步阻塞事件循环
    await tk

    gaps = [round((ticks[i+1] - ticks[i]) * 1000) for i in range(len(ticks)-1)]
    print("ticker 间隔(ms):", gaps)

asyncio.run(main())
```

实测输出：

```text
ticker 间隔(ms): [57, 63, 316, 60, 65, 64, 60]
```

那个 **316ms** 就是被 `time.sleep(0.3)` 卡住的时间。ticker 本该每 50ms 跳一次，却被硬生生拖住了 316 毫秒。**在 asyncio 里，一个同步阻塞调用会冻结整个进程的所有协程**——不是"这个接口变慢"，是"全都停摆"。

### 2.3 并发收益有多大

```python
import asyncio
import time

async def job(name, delay):
    await asyncio.sleep(delay)
    return name

async def main():
    t = time.perf_counter()
    await job("x", 0.3)
    await job("y", 0.3)
    print(f"串行: {time.perf_counter() - t:.2f}s")

    t = time.perf_counter()
    await asyncio.gather(job("x", 0.3), job("y", 0.3))
    print(f"并发: {time.perf_counter() - t:.2f}s")

asyncio.run(main())
```

实测：

```text
串行: 0.61s
并发: 0.31s
```

注意：**并发不等于加速**。总耗时从 0.61 降到 0.31，省下的是"等待时间重叠"，不是把计算变快。如果 `job` 里是 CPU 计算，gather 一点都不会省。

---

## 三、调度层：Task 的行为细节

### 3.1 创建了不 `await`，会怎样

```python
async def main():
    async def long_job():
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            print("  [task] 收到 CancelledError，被取消")
            raise

    task = asyncio.create_task(long_job())
    await asyncio.sleep(0)        # 让任务真正跑起来
    return task                   # 故意不 await

leftover = asyncio.run(main())
print("cancelled() =", leftover.cancelled(), "| done() =", leftover.done())
```

实测：

```text
  [task] 收到 CancelledError，被取消
cancelled() = True | done() = True
```

`asyncio.run()` 退出时会**取消所有还没完成的任务**。所以"fire and forget"（只 create_task 不管）在 asyncio 里是不安全的——任务会被静默取消，且不报错。

### 3.2 一个协程对象只能 await 一次

```python
async def main():
    coro = asyncio.sleep(0.01)
    await coro
    await coro       # 第二次

asyncio.run(main())
# RuntimeError: cannot reuse already awaited coroutine
```

协程是**一次性状态机**，跑完就结束了。要重复执行，重新调用函数拿新的协程对象。

### 3.3 TaskGroup：结构化并发（3.11+）

`create_task` 散着写的问题是：谁负责等它们？失败了怎么办？`TaskGroup` 把"一组任务"当成一个整体：

```python
async def main():
    async with asyncio.TaskGroup() as tg:
        t1 = tg.create_task(job("a", 0.1))
        t2 = tg.create_task(job("b", 0.2))
    print(t1.result(), t2.result())     # 出了 with 块，保证都完成了

asyncio.run(main())
# 实测输出: a b
```

它的两条承诺：

| 承诺 | 含义 |
|---|---|
| 出 `with` 时全部结束 | 不用手写 `await` 每个任务 |
| 任一任务失败 → 取消其余 | 不会留下跑飞的兄弟任务 |
| 异常聚合为 `ExceptionGroup` | 多个失败一起报，用 `except*` 处理 |

实测异常路径：

```python
import asyncio

async def boom():
    await asyncio.sleep(0.05)
    raise ValueError("子任务炸了")

async def main():
    msg = None
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(boom())
            tg.create_task(asyncio.sleep(1))
    except* ValueError as eg:
        msg = f"ExceptionGroup 捕获 {len(eg.exceptions)} 个 ValueError"
    print(msg)

asyncio.run(main())
# 实测输出: ExceptionGroup 捕获 1 个 ValueError
```

注意 `except*`（PEP 654）块里**不能写 `return`**，语法直接报错，只能先赋值再返回。

---

## 四、方法地图：按"解决什么问题"分四类

asyncio 的 API 有几十个，硬背没有意义。按用途分四类，遇到问题时按类去查。

### 4.1 启动与调度：让协程跑起来

| 方法 | 作用 | 什么时候用 |
|---|---|---|
| `asyncio.run(main())` | 创建循环、运行、关闭 | **程序入口，只调一次**；不能在协程内部调用 |
| `create_task(coro)` | 把协程排入循环，返回 Task | 需要"并发跑、稍后取结果"或"后台任务" |
| `TaskGroup()` | 一组任务的结构化容器 | 3.11+，凡是"这几个任务要一起成功/一起失败" |
| `sleep(0)` | 主动让出一次，不真正等待 | 长循环里给别的协程让路 |

### 4.2 等待与组合：多个协程怎么收口

| 方法 | 返回什么 | 顺序/失败行为 |
|---|---|---|
| `gather(*aws)` | 结果列表 | **按传入顺序**返回；任一失败立即抛出，但**兄弟任务不会被取消** |
| `as_completed(aws)` | 迭代器（元素需 `await`） | **按完成顺序**返回，适合"谁先好先用" |
| `wait(aws, return_when=...)` | `(done, pending)` 两个集合 | 可设 `FIRST_COMPLETED` / `FIRST_EXCEPTION` / `ALL_COMPLETED` |
| `wait_for(aw, timeout)` | 结果或抛 `TimeoutError` | 超时会**取消**被等的协程 |
| `timeout(d)` | 上下文管理器（3.11+） | 超时抛 `TimeoutError`，写法比 `wait_for` 更自然 |
| `shield(aw)` | 结果 | 外层被取消时**保护**内部不被取消 |

顺序差异实测：

```python
import asyncio

async def tracked(name, delay):
    await asyncio.sleep(delay)
    return name

async def main():
    res = await asyncio.gather(tracked("slow", 0.3), tracked("fast", 0.1))
    print("gather 顺序:", res)

    order = []
    for fut in asyncio.as_completed([tracked("slow2", 0.3), tracked("fast2", 0.1)]):
        order.append(await fut)
    print("完成顺序:", order)

asyncio.run(main())
# 实测输出:
#   gather 顺序: ['slow', 'fast']    ← 按传入顺序
#   完成顺序: ['fast2', 'slow2']     ← 按完成顺序
```

**`gather` 失败时兄弟任务继续跑**，这一点和 `TaskGroup` 相反，实测确认：

```text
gather 抛出 ValueError('boom')，此时另一任务是否已完成: True
```

也就是说 `gather` 只是"把结果收上来"，不负责"让这组任务同生共死"。要后者就用 `TaskGroup`。

超时的两种写法：

```python
import asyncio

async def main():
    try:
        await asyncio.wait_for(asyncio.sleep(1), timeout=0.1)
    except TimeoutError:
        print("wait_for 超时")

    try:
        async with asyncio.timeout(0.1):     # 可以包住多行
            await asyncio.sleep(1)
            await asyncio.sleep(1)
    except TimeoutError:
        print("timeout 超时")

asyncio.run(main())
# 实测输出:
#   wait_for 超时
#   timeout 超时
```

两者实测都抛 `TimeoutError`。

### 4.3 同步原语与队列：协程之间共享状态

| 原语 | 对应线程版 | 用途 |
|---|---|---|
| `Lock` | `threading.Lock` | 保护临界区（比如限制同时写文件） |
| `Semaphore(n)` | `threading.Semaphore` | **限流**：最多 n 个并发 |
| `Event` | `threading.Event` | 一个协程等另一个协程发信号 |
| `Condition` | `threading.Condition` | 更复杂的等待/通知 |
| `Queue` | `queue.Queue` | 生产者-消费者，用 `await q.get()` |

`Semaphore` 限流实测（6 个任务，上限 2）：

```python
import asyncio

async def main():
    sem = asyncio.Semaphore(2)
    state = {"cur": 0, "peak": 0}

    async def worker():
        async with sem:                    # 最多 2 个协程同时进入
            state["cur"] += 1
            state["peak"] = max(state["peak"], state["cur"])
            await asyncio.sleep(0.15)
            state["cur"] -= 1

    await asyncio.gather(*[worker() for _ in range(6)])
    print("峰值并发:", state["peak"])

asyncio.run(main())
# 实测输出: 峰值并发: 2
```

**这些原语只在同一个事件循环内有效**，不能拿去同步线程。需要跨线程时用 `threading` 的锁。

### 4.4 桥接阻塞代码：把同步函数塞进异步世界

| 方法 | 版本 | 说明 |
|---|---|---|
| `to_thread(func, *args)` | 3.9+ | 把同步函数丢到线程池执行，等待时不阻塞循环 |
| `run_in_executor(executor, func, *args)` | 早期 | 同上，可指定线程池/进程池 |

```python
def blocking():          # 同步阻塞函数，比如 requests.get
    time.sleep(0.3)
    return "done"

async def main():
    t = time.perf_counter()
    r = await asyncio.to_thread(blocking)
    print(r, f"{time.perf_counter()-t:.2f}s")
```

实测耗时 `0.31s`，且**不卡事件循环**——因为实际执行发生在另一个线程，主循环照常调度其他协程。

这是处理 `requests`、`pymysql` 这类不支持异步的库的最短路径。但它不是银弹，见下一节边界。

### 4.5 观察与调试

| 方法 | 用途 |
|---|---|
| `current_task()` | 拿到当前 Task（有 `.get_name()` / `.cancel()`） |
| `all_tasks()` | 当前循环里所有存活 Task，排查"任务泄漏" |
| `get_running_loop()` | 拿到循环对象，底层操作时用 |
| `iscoroutinefunction(f)` | 判断是不是 `async def`（写装饰器/适配层常用） |
| `asyncio.run(main(), debug=True)` | 开启慢回调告警，抓"哪里卡了循环" |

实测：`current_task().get_name()` 返回 `Task-1`；`len(all_tasks())` 在 `main` 内部为 1（只有自己）。

---

## 五、边界：什么时候不该用 asyncio

| 边界 | 表现 | 实测依据 |
|---|---|---|
| **CPU 密集无效** | 计算不 `await`，循环无法切换 | 并发只对"等待"有效；GIL 让多线程也帮不上 |
| **一个同步调用冻结全局** | 所有协程一起停 | ticker 出现 316ms 空档 |
| **不是并行** | 单线程，同一时刻只有一个协程在跑 | 开多少个协程都只占一个 CPU 核 |
| **调试更难** | 堆栈跨协程断开，报错位置不直观 | 用 `debug=True` 辅助 |
| **版本门槛** | `TaskGroup` / `timeout` 需 3.11+，`to_thread` 需 3.9+ | — |
| **生态依赖** | 很多库仍只有同步驱动 | 只能用 `to_thread` 兜底 |

**判断口诀**：你的时间花在"等"（网络、磁盘、数据库）→ asyncio 合适；花在"算"（循环、加解密、图像处理）→ 用多进程。

---

## 六、对比表：asyncio / 线程 / 进程

| 维度 | asyncio | threading | multiprocessing |
|---|---|---|---|
| 并发单位 | 协程（用户态） | 线程（OS 调度） | 进程 |
| 切换成本 | 极低（无内核参与） | 中（内核切换） | 高（进程创建） |
| 单实例内存 | 约 1~2 KB | 约 5~8 MB（栈） | 几十 MB |
| 可同时挂起 | 万级 | 千级 | CPU 核数级 |
| 适用 | **I/O 密集** | I/O + 少量阻塞库 | **CPU 密集** |
| 需要锁吗 | 需要（仍有竞态，只是少） | 需要 | 需要（跨进程要 IPC） |
| 被谁打断 | 只有 `await` 处（协作式） | 随时（抢占式） | — |

注意第三行最后一点：**asyncio 的"不需要锁"是个误解**。单线程只在"没有 `await` 的连续代码段内"才有原子性，一旦中间有 `await`，另一个协程就可能插进来改共享状态。

---

## 七、常见误解

1. **原以为** `await` 是"等待"、会把线程阻塞住，**实际**它的作用是**让出**：挂起自己，把控制权交回循环，让别的协程先跑。`await` 期间这个协程一点 CPU 都不占。
2. **原以为** 用了 asyncio 代码就会变快，**实际**它只让"等待时间重叠"。CPU 计算放进协程里，耗时和不写异步一模一样，还多了调度开销。
3. **原以为** `async def` 里调用同步函数只是"有点慢"，**实际**它会冻结整个事件循环里的所有协程——实测中 0.3 秒的 `time.sleep` 让 ticker 卡出 316ms 空档。
4. **原以为** `gather` 里一个任务失败会把其他任务一起取消，**实际**不会，兄弟任务继续跑完（实测 `True`）；需要"同生共死"用 `TaskGroup`。

---

## 八、自检问题

1. ticker 那个 316ms 空档，如果必须调用那个同步函数，有哪两种改法？各自代价是什么？
2. `asyncio.gather` 和 `TaskGroup` 在"一个任务失败"时的行为不同。你的场景是"批量查 10 个接口，允许部分失败"还是"转账，必须全成功"？分别该用哪个？

第 2 题的答案会把你带到"结构化并发"这个概念上：**`TaskGroup` 管的不是任务，是"任务之间的生死关系"**。

---

## 九、总结

| 问题 | 答案 |
|---|---|
| asyncio 靠什么并发 | 单线程里，在 `await` 处切换协程 |
| 协程 / Task / 循环 | 协程是值；Task 是排入循环的协程；循环是调度器 |
| `await` 做了什么 | 挂起自己 + 注册回调 + 交还控制权 |
| 什么时候会卡死全局 | 协程里出现同步阻塞调用（无 `await`） |
| 多个协程怎么收口 | `gather`（按顺序）/ `as_completed`（按完成）/ `TaskGroup`（同生共死） |
| 同步库怎么办 | `to_thread` / `run_in_executor` |
| 什么时候不该用 | CPU 密集、需要真并行、生态全是同步驱动 |

> **asyncio = 一个循环 + 一堆可暂停的帧。** 并发不是"同时做很多事"，而是"等的时候不闲着"。

## 十、呼应章节

- chapter11 `同步异步与阻塞非阻塞详解.md`：四个象限的区分，本文的 `await` 属于"异步非阻塞"
- chapter12 `Python生成器运行逻辑详解.md`：`await` 底层就是 `yield from` 的同一套帧挂起/恢复
- chapter12 `Python协程详解及与Go、Java对比.md`：协程栈帧的内存开销与三语言差异
- chapter10 `Python中的GIL详解.md`：为什么 asyncio 不能做 CPU 并行
- 本文与 FastAPI：`async def` 路由跑在 ASGI 服务器（uvicorn）的事件循环里，路由内写同步调用，卡的就是这个循环
