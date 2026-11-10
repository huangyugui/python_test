# Python 多线程编程详解

> 上一节：[Python中的GIL详解](01Python中的GIL详解.md)（多线程为什么不能并行）

## 1. threading 模块基础

创建线程有两种方式：

```python
import threading

# 方式一：传 target 函数（常用）
def worker(name):
    print(f"{name} 运行在 {threading.current_thread().name}")

t = threading.Thread(target=worker, args=("任务A",), name="线程-A")
t.start()   # 启动线程
t.join()    # 主线程阻塞，等待它结束
```

```python
# 方式二：继承 Thread，重写 run（适合逻辑复杂、要复用的场景）
class MyThread(threading.Thread):
    def run(self):
        print(f"{threading.current_thread().name} 执行中")

MyThread(name="线程-B").start()
```

四个必须搞清的点：

- **`start()` vs `run()`**：`start()` 才会创建新线程并在其中执行 `run()`；直接调 `t.run()` 只是普通函数调用，还在当前线程里跑。
- **`join(timeout)`**：阻塞等待线程结束，是"等待"不是"开始"。
- **守护线程 `daemon=True`**：主线程退出时守护线程被强制杀死，不会执行 `finally` 清理；默认非守护，主线程会等所有非守护线程跑完才退出。日志线程、心跳线程常用。
- 常用工具：`threading.current_thread()`、`enumerate()`（列出所有活线程）、`threading.local()`（线程私有数据，各线程各存各的）。

## 2. 为什么需要锁：竞态条件

有 GIL 不是就不用加锁了。看这个经典反例：

```python
import threading

counter = 0

def increment():
    global counter
    for _ in range(100_000):
        counter += 1   # 不是原子操作！

t1 = threading.Thread(target=increment)
t2 = threading.Thread(target=increment)
t1.start(); t2.start()
t1.join(); t2.join()
print(counter)   # 经常小于 200000，每次结果还不一样
```

原因：`counter += 1` 在字节码层面是"读取 → 加 1 → 写回"三步。GIL 保证**同一时刻只有一个线程在执行字节码**，但线程随时可能在两条字节码之间被切换（默认每 5ms 切换一次）。两个线程可能都读到旧值 100，各自加 1 后都写回 101——白干了一次。

所以关键结论是：**GIL 保护的是解释器内部状态（比如引用计数），不保护你的业务数据**。只有 `list.append(x)`、`d[k] = v` 这类单条字节码完成的操作才算"天然原子"，任何"检查再操作"的复合逻辑都必须加锁。

## 3. Lock（互斥锁）

最基础的同步原语，同一时刻只允许一个线程持有：

```python
lock = threading.Lock()

def increment():
    global counter
    for _ in range(100_000):
        with lock:          # 推荐写法
            counter += 1
        # 等价于 lock.acquire() ... finally: lock.release()
```

要点：

- `with lock` 是标准写法，即使中间抛异常也会释放；手动 `acquire()/release()` 容易漏。
- 未持锁调用 `release()` 抛 `RuntimeError`。
- **死锁**：线程 A 持锁 1 等锁 2，线程 B 持锁 2 等锁 1，互相卡死。规避方法：所有线程按相同顺序加锁；或 `acquire(timeout=...)` 拿不到就放弃重来。

## 4. RLock（可重入锁）

普通 Lock 有个麻烦：**同一线程**对它 `acquire()` 第二次也会死锁（自己等自己）。RLock 允许同一线程多次加锁，内部计数，必须等量 `release()` 才真正放开：

```python
rlock = threading.RLock()

class Account:
    def __init__(self):
        self.balance = 0
        self._lock = rlock

    def add(self, n):
        with self._lock:
            self.balance += n

    def add_twice(self, n):
        with self._lock:   # 已持有，内部再拿同一把锁不会死锁
            self.add(n)
            self.add(n)
```

如果这里用普通 `Lock`，`add_twice` 里再调 `add` 就死锁了。适用场景：类内部多个方法互相调用、递归中都要持锁。

## 5. Semaphore（信号量）

内部一个计数器：`acquire()` 减 1，减到 0 后阻塞；`release()` 加 1 并唤醒等待者。用来**限制同时访问某资源的线程数**：

```python
import threading, time

sem = threading.Semaphore(3)   # 最多允许 3 个线程同时进入

def access(i):
    with sem:
        print(f"{i} 获得访问权")
        time.sleep(2)          # 模拟访问数据库/接口

ts = [threading.Thread(target=access, args=(i,)) for i in range(10)]
# 10 个线程，但任意时刻最多 3 个在执行 with 块内的代码
```

- 典型场景：连接池、限流（"最多同时 3 个请求打到下游"）。
- 用 **`BoundedSemaphore`** 更保险：release 次数超过初始值会报错，能暴露代码里多释放的 bug；普通 `Semaphore` 的计数器可以无限涨。

## 6. Condition（条件变量）

让线程"等某个条件成立再干活"。**必须先持有锁**才能调用 `wait()/notify()`，否则 `RuntimeError`。

- `wait()`：释放锁 → 阻塞 → 被 notify 唤醒后**重新拿锁** → 返回
- `notify()`：唤醒一个等待线程；`notify_all()`：唤醒全部

经典生产者-消费者（有界缓冲区，这是 Condition 的本职场景）：

```python
import threading

buffer = []
MAX = 5
cond = threading.Condition()   # 默认内部自带 RLock

def producer():
    for i in range(10):
        with cond:
            while len(buffer) == MAX:   # 注意：while 不是 if！
                cond.wait()             # 满了就睡，等消费者唤醒
            buffer.append(i)
            print(f"生产 {i}，库存 {len(buffer)}")
            cond.notify_all()

def consumer():
    for _ in range(10):
        with cond:
            while not buffer:
                cond.wait()             # 空了就睡
            item = buffer.pop(0)
            print(f"消费 {item}，库存 {len(buffer)}")
            cond.notify_all()
```

两个关键点：

1. **条件判断必须用 `while` 不能用 `if`**：被唤醒后，条件可能已经被抢到的另一个线程改变了（存在虚假唤醒的可能），所以醒来后要重新检查条件。
2. `Condition(lock=...)` 可以传入自己已有的 Lock/RLock，不传就内部自带一个 RLock。

## 7. queue.Queue（线程安全队列）

上面 Condition 版生产者-消费者，实际开发中几乎不手写——`queue.Queue` 把"缓冲区 + 锁 + 条件变量"全部打包好了：

```python
import queue, threading

q = queue.Queue(maxsize=5)   # 有界队列；不传 maxsize 就是无限队列

def producer():
    for i in range(10):
        q.put(i)             # 队列满则阻塞（put_nowait 满了抛 queue.Full）
    q.put(None)              # "毒丸"：通知消费者该下班了

def consumer():
    while True:
        item = q.get()       # 队列空则阻塞（get_nowait 抛 queue.Empty）
        if item is None:
            break
        print(f"消费 {item}")
        q.task_done()        # 每处理完一个 get 的任务就配对调用一次

t1 = threading.Thread(target=producer)
t2 = threading.Thread(target=consumer)
t1.start(); t2.start()
t1.join(); t2.join()
```

还有一组"主线程等待全部处理完"的配合技：

- `q.join()`：阻塞直到队列里**每个取出的任务都被 `task_done()` 过**，即全部处理完
- 业务代码里看不到一行锁操作——这就是它取代手写 Condition 的原因

变体：`LifoQueue`（后进先出，栈）、`PriorityQueue`（按优先级出队，元素需可比较）。

## 8. ThreadPoolExecutor（线程池）

手动管理线程的问题：创建销毁有开销、线程数量失控（来 1000 个任务开 1000 个线程）、收集结果麻烦。线程池复用固定数量的线程，统一收集结果：

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def fetch(url):
    time.sleep(1)              # 模拟网络请求（I/O 密集，等的时候释放 GIL）
    return f"{url} 完成"

# 方式一：submit 返回 Future，as_completed 谁先完成先处理谁
with ThreadPoolExecutor(max_workers=5) as pool:
    futures = {pool.submit(fetch, f"url_{i}"): f"url_{i}" for i in range(10)}
    for future in as_completed(futures):
        print(future.result())
```

```python
# 方式二：map——结果按提交顺序返回，写法更像普通 map
with ThreadPoolExecutor(max_workers=5) as pool:
    for r in pool.map(fetch, [f"url_{i}" for i in range(10)]):
        print(r)
```

Future 对象的关键 API：

- `result(timeout)`：阻塞取结果；**如果任务里抛了异常，会在这里重新抛出**——只 `submit()` 从不看 `result()` 会把异常"吞"掉，这是最常见的坑
- `done()` / `cancelled()` / `running()`
- `add_done_callback(fn)`：任务完成后自动回调

异常处理示例：

```python
def bad():
    raise ValueError("出错了")

with ThreadPoolExecutor() as pool:
    f = pool.submit(bad)
    try:
        f.result()             # 异常延迟到这里才抛
    except ValueError as e:
        print("捕获:", e)
```

其他要点：

- 默认 `max_workers = min(32, os.cpu_count() + 4)`
- `with` 块结束自动 `shutdown(wait=True)`，等所有任务跑完
- `concurrent.futures.wait(futures)` 等全部完成；`as_completed(futures, timeout)` 可设超时
- **`ProcessPoolExecutor` 是同一套 API 的进程版**，把 `ThreadPoolExecutor` 换个类名就能绕开 GIL 跑 CPU 密集任务

## 9. 工具选择速查

| 工具 | 解决的问题 | 典型场景 |
|---|---|---|
| `threading.Thread` | 线程的创建与管理 | 少量简单后台任务 |
| `Lock` | 保护共享数据的原子性 | 计数器、状态更新 |
| `RLock` | 同一线程需要重复加锁 | 类方法互相调用、递归 |
| `Semaphore` | 限制同时访问资源的数量 | 连接池、限流 |
| `Condition` | 按条件等待/唤醒 | 有界缓冲、自定义协作逻辑 |
| `queue.Queue` | 打包好的安全数据交接 | 生产者-消费者（首选） |
| `ThreadPoolExecutor` | 复用线程 + 收集结果 | 批量 I/O 任务（实际开发首选） |

## 10. 实战建议

1. 优先用 `ThreadPoolExecutor` 和 `queue.Queue`，少手写裸线程和裸锁——库帮你处理好了大部分同步细节
2. 能不共享数据就不共享；要共享就加锁，锁的粒度尽量小（只包住临界区）
3. 另有两个常用小工具：`Event`（"广播开关"，一个线程 `set()`、多个线程 `wait()`，常用于等初始化完成）和 `threading.local()`（线程私有数据）
4. CPU 密集任务换 `ProcessPoolExecutor`（GIL 限制）；高并发网络 I/O 考虑 asyncio

---

## 11. 各类常用方法速查表

### 11.1 Thread

| 方法 / 属性 | 说明 |
|---|---|
| `Thread(target=None, args=(), kwargs={}, name=None, daemon=None)` | 创建线程 |
| `start()` | 启动线程，**每个线程只能调一次**（否则 RuntimeError） |
| `run()` | 线程体，子类重写；直接调用不创建新线程 |
| `join(timeout=None)` | 等待线程结束；`is_alive()` 为 False 后再 join 才有意义 |
| `is_alive()` | 是否存活（start 之后、run 结束之前） |
| `name` | 线程名（默认 Thread-N），便于日志排查 |
| `daemon` | 守护标志，**必须在 start() 之前设置** |
| `ident` / `native_id` | 线程标识 / 操作系统层线程 ID，start 后才有效 |

### 11.2 Lock 与 RLock

| 方法 | Lock | RLock |
|---|---|---|
| `acquire(blocking=True, timeout=-1)` | 拿锁；`blocking=False` 非阻塞，超时拿不到返回 False | 同左，**同一线程可重复 acquire**（内部计数 +1） |
| `release()` | **任何线程都能释放**；未持锁时释放抛 RuntimeError | 只有**持有者线程**能释放；计数减到 0 才真正放开 |
| `locked()` | 查询是否被持有 | 无此方法 |

> 核心差别记忆：Lock 是"一次一人、谁来都能开门"；RLock 是"同一线程可反复进，必须本人锁门，进出次数要配平"。

### 11.3 Condition

| 方法 | 说明 |
|---|---|
| `Condition(lock=None)` | 可传入已有 Lock/RLock；不传默认自建 RLock |
| `acquire()` / `release()` | 操作内部关联的锁（wait/notify 前必须先拿到） |
| `wait(timeout=None)` | **释放锁并阻塞**；被 notify 唤醒或超时后重新拿锁再返回 |
| `wait_for(predicate, timeout=None)` | 循环 wait 直到 `predicate()` 为 True——推荐用法，替代手写 while 循环；返回 predicate 的最后一次结果 |
| `notify(n=1)` | 唤醒 n 个等待者；**不会释放锁**，要等自己退出 with 块对方才真正继续 |
| `notify_all()` | 唤醒全部等待者 |

### 11.4 Semaphore / BoundedSemaphore

| 方法 | 说明 |
|---|---|
| `Semaphore(value=1)` | 计数器初值，即同时允许的线程数 |
| `BoundedSemaphore(value=1)` | release 次数超过初值时抛 ValueError，能暴露多余释放的 bug |
| `acquire(blocking=True, timeout=None)` | 计数 -1；减到 0 后阻塞（或超时返回 False） |
| `release()` | 计数 +1，唤醒一个等待者；普通版可无限 +1 |

### 11.5 Event（事件 / 广播开关）

| 方法 | 说明 |
|---|---|
| `set()` | 标志置 True，**唤醒所有** wait 的线程（广播，区别于 notify 只唤醒一个） |
| `clear()` | 标志置 False |
| `is_set()` | 查询标志 |
| `wait(timeout=None)` | 阻塞直到 set()；已 set 则立即返回 True，超时返回 False |

### 11.6 queue.Queue 及变体

| 方法 | 说明 |
|---|---|
| `Queue(maxsize=0)` | maxsize<=0 表示无限大 |
| `put(item, block=True, timeout=None)` / `put_nowait(item)` | 队列满则阻塞 / 立即抛 `queue.Full` |
| `get(block=True, timeout=None)` / `get_nowait()` | 队列空则阻塞 / 立即抛 `queue.Empty` |
| `task_done()` | 与一次 get 配对，标记该任务处理完成 |
| `join()` | 阻塞直到未完成任务计数归零（每个 get 都要 task_done） |
| `qsize()` / `empty()` / `full()` | 近似状态查询；**存在竞态，别拿 empty()/full() 当判断依据** |
| `shutdown(immediate=False)` | 3.13+：不再接收新任务，消费者 get 会抛 `queue.ShutDown` |
| `LifoQueue` / `PriorityQueue` | 同一套 API；后进先出 / 按优先级出队 |
| `SimpleQueue` | 轻量版：只有 put/get/empty/qsize，无 task_done/join |

> PriorityQueue 的元素必须可比较；对象任务常用 `(priority, seq, item)` 三元组，用 seq 避免 priority 相同时去比较 item 本身。

### 11.7 ThreadPoolExecutor 与 Future

| 方法 | 说明 |
|---|---|
| `ThreadPoolExecutor(max_workers=None, thread_name_prefix='', initializer=None, initargs=())` | 默认 `min(32, os.cpu_count() + 4)`；initializer 在每个工作线程启动时先执行 |
| `submit(fn, *args, **kwargs)` | 提交一个任务，立即返回 Future |
| `map(fn, *iterables, timeout=None)` | 批量提交，结果**按提交顺序**返回；迭代到某结果时异常才会抛出 |
| `shutdown(wait=True, cancel_futures=False)` | 不再接收新任务；cancel_futures=True 同时取消还没开始的任务（3.9+） |
| `with` 语句 | 自动 `shutdown(wait=True)` |

| Future 方法 | 说明 |
|---|---|
| `result(timeout=None)` | 阻塞取结果；**任务抛的异常在这里重新抛出** |
| `exception(timeout=None)` | 返回任务抛的异常对象但**不抛出**；没异常返回 None |
| `done()` / `running()` / `cancelled()` | 状态查询 |
| `cancel()` | 尝试取消**尚未开始**的任务，成功返回 True；正在跑或已完成返回 False |
| `add_done_callback(fn)` | 完成后回调 `fn(future)`；回调里抛的异常只记日志，不影响主流程 |

### 11.8 concurrent.futures 模块级函数

| 函数 | 说明 |
|---|---|
| `as_completed(fs, timeout=None)` | 迭代器，**哪个 Future 先完成先产出谁** |
| `wait(fs, timeout=None, return_when=ALL_COMPLETED)` | 等待一批任务；`return_when` 可选 `FIRST_COMPLETED` / `FIRST_EXCEPTION` / `ALL_COMPLETED`，返回 (done, not_done) 两个集合 |

### 11.9 threading 模块级函数

| 函数 / 属性 | 说明 |
|---|---|
| `current_thread()` / `main_thread()` | 当前线程对象 / 主线程对象 |
| `enumerate()` / `active_count()` | 所有存活线程的列表 / 数量 |
| `get_ident()` / `get_native_id()` | 当前线程标识 / OS 层线程 ID |
| `setswitchinterval(seconds)` | GIL 线程切换检查间隔，默认 0.005 秒 |
| `stack_size(size)` | 设置新建线程的栈大小 |
| `local()` | 线程本地存储：实例的属性各线程各一份 |
| `excepthook` | 子线程未捕获异常的全局钩子（默认只打印到 stderr，3.8+） |
