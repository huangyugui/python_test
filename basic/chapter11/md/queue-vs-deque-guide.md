# Python Queue 与 Deque 深度对比

## 一、核心概念

### 1.1 Deque (collections.deque)

**双端队列（Double-Ended Queue）**，支持从两端高效地添加和删除元素。

```python
from collections import deque

d = deque([1, 2, 3])
d.append(4)        # 右端添加: [1, 2, 3, 4]
d.appendleft(0)    # 左端添加: [0, 1, 2, 3, 4]
d.pop()            # 右端删除: 4
d.popleft()        # 左端删除: 0
```

**底层实现**：双向链表 + 块数组（block array），O(1) 的两端操作。

---

### 1.2 Queue (queue.Queue)

**线程安全的 FIFO 队列**，专为多线程生产者-消费者模型设计。

```python
import queue

q = queue.Queue(maxsize=10)
q.put(item)        # 放入元素（阻塞直到有空位）
item = q.get()     # 取出元素（阻塞直到有数据）
```

**底层实现**：`collections.deque` + `threading.Condition`（条件变量）。

---

## 二、详细对比

| 特性 | `collections.deque` | `queue.Queue` |
|------|---------------------|---------------|
| **线程安全** | ❌ 非线程安全 | ✅ 线程安全 |
| **阻塞操作** | ❌ 不支持 | ✅ 支持（put/get 可阻塞） |
| **超时控制** | ❌ 不支持 | ✅ 支持（timeout 参数） |
| **容量限制** | ✅ maxlen 参数 | ✅ maxsize 参数 |
| **访问方式** | 双端（FIFO/LIFO/随机） | 仅 FIFO |
| **性能** | ⚡⚡⚡ 极快（C 实现） | ⚡⚡ 较快（有锁开销） |
| **适用场景** | 单线程算法、缓存 | 多线程通信 |

---

## 三、Deque 深度解析

### 3.1 基本操作

```python
from collections import deque

# 创建
d = deque()                    # 空队列
d = deque([1, 2, 3])           # 初始化
d = deque(maxlen=5)            # 固定长度（超出自动丢弃旧元素）

# 添加元素
d.append(x)          # O(1) - 右端添加
d.appendleft(x)      # O(1) - 左端添加
d.extend([1, 2, 3])  # O(k) - 右端批量添加
d.extendleft([1, 2]) # O(k) - 左端批量添加

# 删除元素
d.pop()              # O(1) - 右端删除
d.popleft()          # O(1) - 左端删除
d.remove(value)      # O(n) - 删除第一个匹配值
d.clear()            # O(n) - 清空

# 查询
len(d)               # O(1)
d[0], d[-1]          # O(1) - 访问两端
d[5]                 # O(n) - 随机访问（慢！）
value in d           # O(n) - 成员检查

# 其他
d.rotate(1)          # 右旋转：[1,2,3] → [3,1,2]
d.rotate(-1)         # 左旋转：[1,2,3] → [2,3,1]
d.count(value)       # 统计出现次数
d.copy()             # 浅拷贝
```

### 3.2 maxlen 特性

```python
d = deque(maxlen=3)
d.append(1)  # [1]
d.append(2)  # [1, 2]
d.append(3)  # [1, 2, 3]
d.append(4)  # [2, 3, 4]  ← 自动丢弃最左边的 1
```

**应用场景**：
- 滑动窗口算法
- 最近 N 条记录缓存
- BFS 路径跟踪

### 3.3 性能特点

```python
import time
from collections import deque

# 测试 append/popleft 性能
d = deque()
start = time.time()
for i in range(1_000_000):
    d.append(i)
for i in range(1_000_000):
    d.popleft()
print(f"deque: {time.time() - start:.3f}s")  # ~0.1s

# 对比 list
lst = []
start = time.time()
for i in range(1_000_000):
    lst.append(i)
for i in range(1_000_000):
    lst.pop(0)  # O(n) - 极慢！
print(f"list: {time.time() - start:.3f}s")   # ~50s
```

**关键结论**：
- ✅ `deque.append/popleft`：**O(1)**
- ❌ `list.pop(0)`：**O(n)**（需要移动所有元素）

---

## 四、Queue 深度解析

### 4.1 基本操作

```python
import queue

# 创建
q = queue.Queue()           # 无限容量
q = queue.Queue(maxsize=10) # 有限容量

# 放入元素
q.put(item)                 # 阻塞直到有空位
q.put(item, block=False)    # 非阻塞，满时抛 Full 异常
q.put(item, timeout=2.0)    # 最多等待 2 秒

# 取出元素
item = q.get()              # 阻塞直到有数据
item = q.get(block=False)   # 非阻塞，空时抛 Empty 异常
item = q.get(timeout=2.0)   # 最多等待 2 秒

# 快捷方式
q.put_nowait(item)          # = q.put(item, block=False)
item = q.get_nowait()       # = q.get(block=False)

# 状态查询
q.qsize()                   # 近似大小（不精确！）
q.empty()                   # 是否为空（不可靠！）
q.full()                    # 是否已满（不可靠！）
```

### 4.2 任务追踪机制

```python
import queue
import threading

def worker(q):
    while True:
        item = q.get()
        if item is None:
            break
        process(item)
        q.task_done()  # 标记任务完成

q = queue.Queue()
threads = [threading.Thread(target=worker, args=(q,)) for _ in range(5)]
for t in threads:
    t.start()

# 放入任务
for item in items:
    q.put(item)

# 等待所有任务完成
q.join()  # 阻塞直到所有 task_done() 被调用

# 停止工作线程
for _ in threads:
    q.put(None)
for t in threads:
    t.join()
```

**核心方法**：
- `task_done()`：标记一个任务完成
- `join()`：阻塞直到所有任务完成

### 4.3 底层实现原理

```python
import threading
from collections import deque
from queue import Full, Empty

# queue.Queue 的真实实现逻辑（简化版）
class RealQueue:
    def __init__(self, maxsize=0):
        self.maxsize = maxsize
        self.queue = deque()
        self.mutex = threading.Lock()
        self.not_empty = threading.Condition(self.mutex)
        self.not_full = threading.Condition(self.mutex)
        self.all_tasks_done = threading.Condition(self.mutex)
        self.unfinished_tasks = 0
    
    def put(self, item, block=True, timeout=None):
        with self.not_full:
            if self.maxsize > 0:
                if not block:
                    if len(self.queue) >= self.maxsize:
                        raise Full
                elif timeout is None:
                    while len(self.queue) >= self.maxsize:
                        self.not_full.wait()
                elif timeout < 0:
                    raise ValueError("'timeout' must be a non-negative number")
                else:
                    endtime = threading._time() + timeout
                    while len(self.queue) >= self.maxsize:
                        remaining = endtime - threading._time()
                        if remaining <= 0.0:
                            raise Full
                        self.not_full.wait(remaining)
            
            self.queue.append(item)
            self.unfinished_tasks += 1
            self.not_empty.notify()  # 唤醒一个等待的消费者
    
    def get(self, block=True, timeout=None):
        with self.not_empty:
            if not block:
                if not self.queue:
                    raise Empty
            elif timeout is None:
                while not self.queue:
                    self.not_empty.wait()
            elif timeout < 0:
                raise ValueError("'timeout' must be a non-negative number")
            else:
                endtime = threading._time() + timeout
                while not self.queue:
                    remaining = endtime - threading._time()
                    if remaining <= 0.0:
                        raise Empty
                    self.not_empty.wait(remaining)
            
            item = self.queue.popleft()
            self.not_full.notify()  # 唤醒一个等待的生产者
            return item
    
    def task_done(self):
        with self.all_tasks_done:
            unfinished = self.unfinished_tasks - 1
            if unfinished < 0:
                raise ValueError('task_done() called too many times')
            self.unfinished_tasks = unfinished
            if unfinished == 0:
                self.all_tasks_done.notify_all()
    
    def join(self):
        with self.all_tasks_done:
            while self.unfinished_tasks:
                self.all_tasks_done.wait()
```

**关键点**：
1. **双 Condition 设计**：`not_empty` 和 `not_full` 分离，避免惊群效应
2. **共享 mutex**：两个 Condition 共用同一个 Lock，确保原子性
3. **超时精确计算**：使用 `endtime - current_time` 避免累积误差
4. **内部使用 `deque`**：保证 O(1) 的两端操作

---

## 五、Queue 的变体

### 5.1 LifoQueue（栈）

```python
import queue

q = queue.LifoQueue()  # Last-In-First-Out
q.put(1)
q.put(2)
q.put(3)
print(q.get())  # 3（最后放入的最先取出）
```

### 5.2 PriorityQueue（优先队列）

```python
import queue

q = queue.PriorityQueue()
q.put((2, "medium"))
q.put((1, "high"))
q.put((3, "low"))
print(q.get())  # (1, "high")（优先级最高的先出）
```

**底层实现**：基于 `heapq` 模块的最小堆实现。

**关键特性**：
1. **元组比较**：优先级由元组的第一个元素决定
2. **相同优先级的处理**：如果第一个元素相同，会比较第二个元素（要求可比较）
3. **时间复杂度**：`put()` 和 `get()` 都是 O(log n)

**注意事项**：
```python
# ❌ 错误：优先级相同且第二个元素不可比较
q.put((1, {"data": "a"}))
q.put((1, {"data": "b"}))  # TypeError: '<' not supported between dicts

# ✅ 正确：添加唯一标识符避免比较第二个元素
import itertools
counter = itertools.count()
q.put((1, next(counter), {"data": "a"}))
q.put((1, next(counter), {"data": "b"}))
```

**适用场景**：
- 任务调度系统（高优先级任务先执行）
- Dijkstra 最短路径算法
- 事件驱动系统中的定时事件

### 5.3 SimpleQueue（简化版，Python 3.7+）

```python
import queue

q = queue.SimpleQueue()  # 无 maxsize、无 task_done/join
q.put(item)
item = q.get()
```

**底层实现**：使用 `_thread.lock`（底层 C 锁）而非 `threading.Condition`。

**与 Queue 的区别**：
| 特性 | `Queue` | `SimpleQueue` |
|------|---------|---------------|
| 容量限制 | ✅ maxsize | ❌ 无限容量 |
| 超时控制 | ✅ timeout | ❌ 不支持 |
| 任务追踪 | ✅ task_done/join | ❌ 不支持 |
| 非阻塞模式 | ✅ block=False | ❌ 仅阻塞 |
| 性能 | 较快 | **最快**（锁开销最小） |

**优势**：
- 更轻量，性能略好（少了一些功能）
- 适合简单的生产者-消费者场景，不需要复杂控制

**源码核心逻辑**：
```python
# SimpleQueue 的简化实现
class _SimpleQueue:
    def __init__(self):
        self._queue = deque()
        self._lock = _thread.allocate_lock()
        self._not_empty = threading.Condition(self._lock)
    
    def put(self, item):
        with self._lock:
            self._queue.append(item)
            self._not_empty.notify()
    
    def get(self):
        with self._not_empty:
            while not self._queue:
                self._not_empty.wait()
            return self._queue.popleft()
```

**注意**：`SimpleQueue` 没有 `maxsize` 参数，因此不存在"满"的状态，`put()` 永远不会阻塞。

---

## 六、使用场景对比

### 6.1 何时用 Deque？

✅ **单线程场景**：
```python
# BFS 广度优先搜索
from collections import deque

def bfs(graph, start):
    visited = set()
    queue = deque([start])
    
    while queue:
        node = queue.popleft()
        if node in visited:
            continue
        visited.add(node)
        queue.extend(graph[node])
```

✅ **滑动窗口**：
```python
def moving_average(data, window_size):
    window = deque(maxlen=window_size)
    averages = []
    
    for value in data:
        window.append(value)
        averages.append(sum(window) / len(window))
    
    return averages
```

✅ **历史记录**：
```python
history = deque(maxlen=100)  # 只保留最近 100 条
history.append(user_action)
```

---

### 6.2 何时用 Queue？

✅ **多线程生产者-消费者**：
```python
import queue
import threading

def generate_items():
    """模拟数据生成"""
    for i in range(100):
        yield f"item_{i}"

def process(item):
    """模拟数据处理"""
    print(f"Processing {item}")

def producer(q):
    for item in generate_items():
        q.put(item)  # 自动阻塞，直到有空位
    q.put(None)  # 发送停止信号

def consumer(q):
    while True:
        item = q.get()  # 自动阻塞，直到有数据
        if item is None:
            break
        process(item)
        q.task_done()

q = queue.Queue(maxsize=100)
producer_thread = threading.Thread(target=producer, args=(q,))
consumer_thread = threading.Thread(target=consumer, args=(q,))
producer_thread.start()
consumer_thread.start()
producer_thread.join()
consumer_thread.join()
```

✅ **任务分发系统**：
```python
q = queue.Queue()

# 主线程放入任务
for task in tasks:
    q.put(task)

# 等待所有任务完成
q.join()  # 阻塞直到所有 task_done() 被调用
```

✅ **限流控制**：
```python
q = queue.Queue(maxsize=10)  # 最多缓冲 10 个请求

def handle_request(request):
    try:
        q.put_nowait(request)  # 满了就拒绝
    except queue.Full:
        return "Service Unavailable"
```

---

## 七、常见陷阱

### 7.1 Deque 陷阱

❌ **随机访问性能差**：
```python
d = deque(range(1_000_000))
d[500_000]  # O(n) - 非常慢！
```

✅ **正确做法**：只用 `d[0]` 和 `d[-1]`

❌ **线程不安全**：
```python
# 多线程环境下直接操作 deque 会导致数据竞争
d = deque()
# Thread 1: d.append(x)
# Thread 2: d.popleft()  # 可能崩溃！
```

✅ **正确做法**：多线程时用 `queue.Queue`

---

### 7.2 Queue 陷阱

❌ **依赖 empty()/full()**：
```python
if not q.empty():  # 不可靠！下一秒可能就空了
    item = q.get()
```

✅ **正确做法**：直接用 `get(timeout=...)` 处理异常

❌ **忘记 task_done()**：
```python
item = q.get()
process(item)
# 忘记 q.task_done() → q.join() 永久阻塞！
```

❌ **qsize() 不精确**：
```python
size = q.qsize()  # 文档明确说明"not reliable"
```

✅ **正确做法**：仅用于监控，不要用于逻辑判断

---

## 八、性能基准测试

```python
import time
from collections import deque
import queue

def benchmark_deque(n=1_000_000):
    """测试 deque 的单线程性能"""
    d = deque()
    start = time.time()
    for i in range(n):
        d.append(i)
    for i in range(n):
        d.popleft()
    return time.time() - start

def benchmark_queue(n=1_000_000):
    """测试 Queue 的单线程性能（无线程竞争）"""
    q = queue.Queue()
    start = time.time()
    for i in range(n):
        q.put(i)
    for i in range(n):
        q.get()
    return time.time() - start

def benchmark_multithread_queue(num_items=100_000, num_producers=4, num_consumers=4):
    """测试多线程环境下的 Queue 性能"""
    q = queue.Queue(maxsize=1000)
    produced = 0
    consumed = 0
    lock = threading.Lock()
    
    def producer():
        nonlocal produced
        for i in range(num_items // num_producers):
            q.put(i)
            with lock:
                produced += 1
    
    def consumer():
        nonlocal consumed
        while True:
            try:
                item = q.get(timeout=0.1)
                with lock:
                    consumed += 1
                q.task_done()
            except queue.Empty:
                if consumed >= num_items:
                    break
    
    start = time.time()
    threads = []
    for _ in range(num_producers):
        t = threading.Thread(target=producer)
        threads.append(t)
        t.start()
    
    for _ in range(num_consumers):
        t = threading.Thread(target=consumer)
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    return time.time() - start

# 执行测试
print("=== 单线程性能对比 ===")
print(f"deque: {benchmark_deque():.3f}s")   # ~0.15s
print(f"queue: {benchmark_queue():.3f}s")   # ~0.8s

print("\n=== 多线程性能测试 ===")
print(f"4生产者+4消费者 (10万条目): {benchmark_multithread_queue():.3f}s")
```

**结论**：
- 单线程场景：`deque` 快 **5-10 倍**（无锁开销）
- 多线程场景：必须用 `queue.Queue`（线程安全优先）
- 典型吞吐量：4生产者+4消费者可达 **50,000-100,000 ops/sec**

---

## 九、总结

### 选择指南

| 场景 | 推荐 | 原因 |
|------|------|------|
| 单线程算法（BFS、滑动窗口） | `deque` | 性能最优 |
| 多线程通信 | `queue.Queue` | 线程安全 + 阻塞 |
| 需要 LIFO | `queue.LifoQueue` | 内置栈语义 |
| 需要优先级 | `queue.PriorityQueue` | 内置堆实现 |
| 高性能单线程缓存 | `deque(maxlen=N)` | 自动淘汰旧数据 |
| 任务追踪 | `queue.Queue` + `task_done()` | 内置支持 |

### 核心区别

- **`deque`**：数据结构，关注**效率**
- **`queue.Queue`**：同步原语，关注**安全**

**黄金法则**：
> 单线程用 `deque`，多线程用 `queue.Queue`，永远不要在多线程中直接使用 `deque`。
