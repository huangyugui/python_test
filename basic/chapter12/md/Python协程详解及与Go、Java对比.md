# Python 协程详解及与 Go、Java 对比

> 本文整理自一次深入讨论：从"什么是协程"出发，逐层展开协程的栈帧存储机制、内存开销，最后横向对比 Python、Go、Java 三者协程实现的差异。

---

## 目录

1. [什么是协程](#一什么是协程)
2. [协程暂停时栈帧存在哪里](#二协程暂停时栈帧存在哪里)
3. [挂起大量协程会占很多内存吗](#三挂起大量协程会占很多内存吗)
4. [Python、Java、Go 协程的核心差异](#四pythonjavago-协程的核心差异)
5. [Go 和 Java 如何自动完成暂停与恢复](#五go-和-java-如何自动完成暂停与恢复)
6. [总结对照表](#六总结对照表)

---

## 一、什么是协程

**协程（Coroutine）**是一种可以在执行过程中**主动暂停和恢复**的函数，是实现并发编程的一种方式。与线程由操作系统调度不同，协程由程序（事件循环）自己调度，切换成本极低。

### 核心特点

1. **协作式并发**：协程只在遇到 `await` 时主动让出控制权，不会像线程那样被强制打断，因此通常不需要加锁。
2. **单线程并发**：一个线程内可以运行成千上万个协程，适合 I/O 密集型任务（网络请求、文件读写等）。
3. **极低的切换开销**：不涉及内核态切换，只是保存/恢复函数栈帧。

### 基本用法

```python
import asyncio

async def say_hello(name):          # async def 定义的就是协程函数
    print(f"Hello, {name}")
    await asyncio.sleep(1)          # await 暂停，让出控制权
    print(f"Bye, {name}")

async def main():
    # 并发运行两个协程
    await asyncio.gather(say_hello("A"), say_hello("B"))

asyncio.run(main())                 # 启动事件循环并运行协程
```

运行 `main()` 时，`say_hello("A")` 执行到 `await asyncio.sleep(1)` 会暂停，事件循环转去执行 `say_hello("B")`，1 秒后两个协程继续执行——总耗时约 1 秒而不是 2 秒。

### 关键概念

| 概念 | 说明 |
|------|------|
| 协程对象 | 调用 `async def` 函数返回的对象（不会立即执行） |
| `await` | 暂停当前协程，等待可等待对象完成 |
| 事件循环 | 调度器，负责在协程之间切换，`asyncio.run()` 会创建它 |
| 可等待对象 | 协程、`Task`、`Future` |

### 协程 vs 生成器 vs 线程

- **生成器**：协程的前身，`yield` 也能暂停，但只能"单向"传递数据；`async/await` 本质上是生成器思想的进化。
- **线程**：操作系统抢占式调度，切换开销大，需要锁保护共享数据。
- **多进程**：适合 CPU 密集型任务，绕开 GIL；协程不适合 CPU 密集型任务。

> 简单总结：**协程 = 单线程里用 `async/await` 实现的"可暂停函数"，靠事件循环实现 I/O 并发**。

---

## 二、协程暂停时栈帧存在哪里

### 结论：栈帧存在堆上，而不是调用栈里

普通函数的栈帧存在于**线程的调用栈**上，函数 `return` 后帧立即销毁。而协程暂停时，它的栈帧会被"冻结"并**保存在堆内存中**，由协程对象持有引用，恢复执行时再放回去继续运行。

### 具体机制

在 CPython 中，每个协程对象本质上和生成器类似，都带有一个帧对象（frame object）：

- 协程对象上有 `cr_frame`（帧对象）、`cr_await`（挂起时在等待什么）、`cr_running` / `cr_suspended` 等状态字段
- 帧里保存了局部变量、指令指针 `f_lasti`（记录暂停在哪条字节码）等
- 整个帧和所有局部变量都活着，直到协程执行完毕被垃圾回收

可以实际验证：

```python
import asyncio

async def coro():
    x = 42
    await asyncio.sleep(1)   # 在这里暂停

async def main():
    c = coro()               # 创建协程对象，还没开始执行
    t = asyncio.create_task(c)
    await asyncio.sleep(0.1) # 此时协程已挂起
    print(t.get_coro().cr_frame.f_locals)  # {'x': 42}
    await t

asyncio.run(main())
# 输出: {'x': 42}  —— 局部变量在堆上的帧对象里
```

### 与普通函数调用对比

```python
def normal():
    x = 42
    return           # 帧销毁，局部变量没了
```

普通函数返回后帧被回收，无法"从返回点继续"；协程暂停时帧只是挂起，**`f_lasti` 记录了恢复的精确位置**，`await` 结束后事件循环调用 `coro.send(value)` 把帧重新压回解释器执行栈继续跑。

### 版本演进

- **Python 3.11 之前**：每帧都是一个完整 frame object，比较重
- **Python 3.11+**：对协程/生成器做了优化，帧数据直接内嵌在协程对象本身的内存结构里（懒物化，挂起时才创建 Python 层可见的 frame object），内存占用显著下降

> **一句话总结**：协程暂停 = 栈帧从执行栈上"摘下来"放进堆内存，由协程对象保管；恢复 = 把帧重新放回执行栈，从 `await` 的位置继续。这也是为什么协程不依赖操作系统栈、可以有百万个同时"挂起"的协程——每个只占几百字节的堆内存。

---

## 三、挂起大量协程会占很多内存吗

### 结论：确实会占内存，但远比线程"便宜"

### 量级对比

| 方式 | 单个挂起的大致内存 |
|------|------|
| 协程（Python 3.11+，局部变量少） | **约 1~2 KB**（协程对象 + 帧 + 局部变量） |
| 线程 | **约 5~8 MB**（默认栈大小，且需内核态资源） |
| 进程 | 几十 MB 起 |

所以同样是"挂起 10 万个任务"：

- 协程：约 **100~200 MB** —— 可接受
- 线程：**500 GB+** —— 完全不可行（线程数实际受限于几千个）

这就是为什么高并发 I/O 场景（一个爬虫同时抓 10 万个网页）只能用协程。

### 内存都花在哪

```python
import sys
import asyncio

async def coro():
    x = 42
    await asyncio.sleep(100)

async def main():
    coros = [coro() for _ in range(10000)]
    print(sys.getsizeof(coros[0]))  # 协程对象本身 ~200 字节
    # 加上 frame、局部变量、Task 包装等，实际约 1-2 KB/个
    await asyncio.wait(coros)
```

开销构成：

- **协程对象本身**：约 200 字节
- **帧 + 局部变量**：取决于局部变量数量、闭包引用了什么
- **Task/Future 包装、事件循环的回调链**：又加几百字节

### 内存膨胀的常见元凶

真正让协程"吃内存"的往往不是协程本身，而是：

1. **持有大对象不放**——挂起的协程里引用了一个几 MB 的 `response`，所有协程都不释放
2. **Task 泄漏**——创建了 Task 却不 `await` 也不取消，永远挂在事件循环上
3. **协程链太深**——`await` 一层层嵌套，`cr_await` 链上每层都有帧
4. **无界的任务列表**——把 100 万个任务塞进列表一次性 `gather`，而不是分批/流式处理

```python
# 不好的写法：一次性创建 100 万个 Task
await asyncio.gather(*[fetch(url) for url in urls])   # 内存峰值巨大

# 好的写法：用信号量或队列控制并发数
sem = asyncio.Semaphore(1000)

async def limited_fetch(url):
    async with sem:
        return await fetch(url)
```

### 与 Go 的对比

Go 语言有更深度的优化：goroutine 栈只有 **2 KB 起步**且按需增长（分段栈/连续栈），所以 Go 能轻松撑起百万级并发——这也是"百万连接"服务器多选 Go/协程框架的原因。Python 3.11 之后的协程已借鉴了类似思路（帧内嵌、懒物化），开销持续下降。

> **一句话总结**：挂起协程确实占内存，但**每个只有 KB 级**，比线程小 3~4 个数量级。协程的内存模型完全能支撑十万级并发；撑不住通常说明代码里有大对象滞留、Task 泄漏或无界并发，而不是协程本身的问题。

---

## 四、Python、Java、Go 协程的核心差异

三者实现并发的思路完全不同，这直接决定了性能、编程风格和适用场景。

### 核心差异总览

| 维度 | Python (asyncio) | Java (虚拟线程，JDK 21+) | Go (goroutine) |
|------|------|------|------|
| 实现方式 | **用户态事件循环**，显式 `async/await` | **JVM 用户态调度**，普通同步代码 | **运行时调度器**，语言级内置 |
| 栈 | 无栈协程，帧存堆上，约 1~2 KB | 虚拟线程有可增长栈，存堆上（StackChunk） | goroutine 栈 **2 KB 起**，按需增长 |
| 调度 | 单线程协作式（主动 `await` 让出） | M:N 调度，**阻塞时自动让出** | M:N 调度，**阻塞/抢占时自动让出** |
| 用法 | 必须显式标注 `async/await`，生态分同步/异步两套 | **无感知**，写普通阻塞代码即可 | **无感知**，`go f()` 一键并发 |
| 调度时机 | 完全由程序员控制 | 阻塞 API 内部 + JVM 插桩 | 阻塞调用 + 异步抢占信号 |
| GIL | 有（3.13 起可选 free-threading） | 无 | 无 |
| CPU 密集型并发 | 不适合 | 适合 | 适合 |
| 起步年代 | 3.5（2015） | Loom → JDK 21（2023） | 1.0（2012） |

### 1. 无栈 vs 有栈（最本质的区别）

**Python：无栈协程**

协程就是"能暂停的函数"，暂停点必须用 `await` 显式标记，状态保存在堆上的帧对象里。

```python
async def fetch():
    r = await http.get(url)   # 必须显式 await
    data = r.json()
    return data["title"]      # 下游也要 async，一路"传染"
```

**Go / Java：有栈协程**

每个执行单元有自己独立的栈（Go 2KB 起可增长；Java 虚拟线程栈存堆上），被阻塞时运行时把整个栈换出，代码可以像写同步程序一样写。

```go
// Go：无需任何标注，go 关键字直接并发
func fetch(url string) {
    resp, _ := http.Get(url)      // 阻塞时调度器自动切换
    body, _ := io.ReadAll(resp.Body)
}
go fetch(url1)
go fetch(url2)                    // 每行代码天然可挂起
```

```java
// Java 21 虚拟线程：写普通阻塞代码
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    executor.submit(() -> {
        var resp = httpClient.send(req);  // 看起来是阻塞调用，
        return handle(resp);              // 实际阻塞时挂起整个虚拟线程
    });
}
```

### 2. "函数染色"问题

这是 Python 与 Go/Java 最直观的差别：

- **Python**：`async` 会"传染"——调用链上每个函数都得是 `async`，库里同步/异步 API 常常要维护两套（如 `requests` vs `aiohttp`）
- **Go/Java**：任何函数都天然可阻塞、可挂起，一套 API 通吃

### 3. 调度策略

- **Python**：纯协作式，单线程事件循环。代码里如果有 CPU 密集的死循环，**整个事件循环卡死**，所有协程都没法跑
- **Go**：抢占式 M:N 调度（1.14 起基于信号的异步抢占），多个 goroutine 自动分配到多核，`GOMAXPROCS` 控制并行度——**真正利用多核**
- **Java**：虚拟线程由 ForkJoinPool 调度到载体线程上，阻塞时自动 unmount，同样能利用多核

### 4. 通信风格

- **Go**：为并发而生哲学——"不要通过共享内存来通信，而要通过通信来共享内存"，内置 `channel`、`select`，语法级一等公民
- **Java**：仍以共享内存 + 锁为主，虚拟线程不改变这个模型；结构化并发（`StructuredTaskScope`）还在预览阶段
- **Python**：`asyncio.Queue`、`Event`、`gather` / `TaskGroup`（3.11 起类似结构化并发）

### 5. 为什么有这样的差异

- **Go**：语言 + 运行时一体设计，goroutine 是核心卖点，调度器和编译器深度优化
- **Java**：要在不改变既有同步 API 和整个生态的前提下获得协程能力，所以 Loom 选择"虚拟线程"路线（对旧代码零侵入）
- **Python**：历史包袱下选择最小侵入方案——生成器演进为 `async/await`，纯库实现（asyncio），依赖显式标记

> **一句话总结**：**Python** 是"显式的无栈协程"，轻量但要求到处写 `async/await`，单线程协作式调度；**Go** 是"语言内置的有栈协程"，2KB 起步、自动调度、真多核，体验最顺滑；**Java** 用"虚拟线程"让阻塞代码自动变成协程，生态零改造成本。三者都为了高并发 I/O，但 Go/Java 是运行时替你做了暂停/恢复，Python 是你自己用 `await` 声明。

---

## 五、Go 和 Java 如何自动完成暂停与恢复

关键点在于：**暂停和恢复都由运行时或 JVM 完成，不需要你在代码里写任何标记**。它们做的事本质相同——把执行现场（寄存器、栈指针、程序计数器）存起来，下次再恢复。

---

### 5.1 Go：goroutine 的暂停与恢复

#### 底层三件套：G、M、P

| 概念 | 含义 |
|------|------|
| **G** | goroutine，保存执行现场的结构体（栈、SP、PC、状态） |
| **M** | OS 线程（machine） |
| **P** | 逻辑处理器，持有可运行 G 的本地队列，数量 = `GOMAXPROCS` |

一个 M 拿到 P，从 P 的队列里取出 G 执行。**一个 goroutine 暂停时，运行时会把它的现场写回 G 结构，把 G 从 M 上摘下来，M 再取下个 G 跑。**

#### 现场保存在哪里：`gobuf`

每个 G 里有一个 `sched gobuf` 字段：

```go
type gobuf struct {
    sp   uintptr  // 栈指针
    pc   uintptr  // 下一条要执行的指令地址
    g    guintptr
    ret  uintptr
    // ...
}
```

暂停时把 CPU 的 SP/PC 存进 `sched`，恢复时再从 `sched` 读回寄存器——和 Python 协程帧里存 `f_lasti` 是一个道理，只是 Go 存的是**整个栈 + 寄存器**。

#### 暂停的两种触发方式

**(a) 主动让出（阻塞操作）**

```go
func fetch() {
    resp, _ := http.Get(url)   // 底层 socket 读
    _ = resp
}
```

`http.Get` 最终走到 `runtime.netpollblock()`：

1. 注册 fd 到 epoll（Linux）
2. 调用 **`gopark()`** —— 运行时函数，把当前 G 状态改为 `_Gwaiting`，保存 sp/pc 到 `sched`，然后 `mcall` 切换到调度循环
3. M 转去执行其他 G，**这个 G 的栈完整保留在堆上**

网络就绪后，netpoller 触发，调用 `goready()` 把 G 放回可运行队列：

```go
func gopark(unlockf func(*g, unsafe.Pointer) bool, lock unsafe.Pointer,
            reason waitReason, traceReason byte, traceskip int)

func goready(gp *g, traceskip int)
```

**(b) 被动抢占（CPU 时间片用完）**

这是 Go 相对 Python 的关键优势。早期只能靠函数序言插入检查点，Go 1.14 后支持**基于信号的异步抢占**：

- 运行时给 M 发送 `SIGURG` 信号
- 信号处理函数中直接把 G 的现场保存并标记为可抢占，`gopreempt_m` → `gosched`
- 所以即使有 CPU 密集的死循环，也能被调度器打断

#### 栈的动态伸缩（有栈协程的核心）

goroutine 栈 **2 KB 起**，不够时：

- 每个函数序言检查 `SP` 是否越过 `stackguard0`
- 越界就调用 `runtime.morestack()`：分配一个**两倍大小的新栈，把旧栈整块 memcpy 过去，修正所有指向旧栈的指针**，然后从原 PC 继续执行

恢复时，只需要把 G 的 `sched.sp` / `sched.pc` 装回寄存器，跳到 `gogo` 汇编桩，就继续跑了：

```asm
// runtime/asm_amd64.s 简化版
TEXT runtime·gogo(SB), NOSPLIT, $0-8
    MOVQ  buf+0(FP), BX
    MOVQ  gobuf_g(BX), DX
    MOVQ  gobuf_sp(BX), SP   // 恢复栈指针
    MOVQ  gobuf_pc(BX), BX
    JMP   BX                 // 跳回暂停前的位置
```

> **一句话**：Go 靠 `gopark` / `goready` + `gobuf` + 栈复制，暂停时整个栈被搬进内存堆里，恢复时 `JMP` 回去。

---

### 5.2 Java：虚拟线程如何自动暂停/恢复

#### 两层结构：Continuation + 虚拟线程

```java
// JDK 内部核心类，不对外暴露（jdk.internal.vm.Continuation）
Continuation c = new Continuation(scope, () -> {
    // 这里面是"虚拟线程的 body"
    socket.read(...);   // 阻塞时自动 yield
});
c.run();                // 启动/恢复
```

- **Continuation**：纯 Java 实现的"可暂停执行单元"，`yield()` 暂停，`run()` 恢复
- **VirtualThread**：`Thread` 的子类，内部组合一个 Continuation，把 `run()` 交给 `ForkJoinPool` 的载体线程（carrier thread）执行

#### 栈不在 OS 线程栈上，而在堆里

虚拟线程用的是**自定义栈块（StackChunk）**，本质是一个 Java 对象（位于堆上），里面按字节保存了帧数据。JDK 20 之后还用上 Loom 的 **freeze / thaw** 优化：暂停时把栈内容冻结成紧凑格式，恢复时解冻回内存布局。

| | 平台线程 | 虚拟线程 |
|--|--|--|
| 栈的位置 | OS 分配的 C 栈，默认 512KB~1MB | **Java 堆上的 StackChunk**，几百字节起 |
| 数量上限 | 几千 | 百万级 |

#### 触发点：谁来判断"该暂停了"

Java 不需要你在代码里加标记，因为 JDK 把**所有可能阻塞的 JDK 方法**都改造成了挂载点（mount / unmount point）：

- `Socket` / `ServerSocket` / `DatagramSocket` 的 I/O
- `FileChannel`、`Selector`
- `LockSupport.park()` / `unpark()`
- `Thread.sleep()`、`Object.wait()`、`Thread.join()`
- `java.util.concurrent` 的阻塞队列、`Future.get()`
- `synchronized` 块（**JDK 21 会钉住线程 pinned，JDK 24 已修复**）

这些方法内部会调用类似 `Continuation.yield()` 的机制：

```java
// 伪代码：socket read 的简化流程
int n = socketRead0(fd, buf);       // 如果返回 WOULD_BLOCK
Blocker b = begin();                // 注册回调到 Poller
while (true) {
    int r = tryRead();
    if (r != WOULD_BLOCK) return r;
    Continuation.yield(VTHREAD_SCOPE);  // ← 暂停，栈冻结进堆
    // 被 park 唤醒后，从这里继续
}
```

调用 `Continuation.yield()` 时，JVM 会：

1. 把当前栈帧冻结（freeze）到 StackChunk
2. **unmount** —— 把载体线程交还给 ForkJoinPool
3. 载体线程去执行别的虚拟线程

I/O 就绪后，Poller 回调触发 `unpark()`：

1. 把虚拟线程重新提交给 ForkJoinPool
2. 载体线程执行 `Continuation.run()`，**thaw** 栈帧
3. 从 `yield` 的下一行代码继续执行

#### 一个关键约束：pinning

如果虚拟线程在 `synchronized` 块里或调用 native 方法时阻塞，它会被**钉住（pinned）**，无法 unmount——此时载体线程会被真阻塞。JDK 21 的常见坑：

```java
synchronized (lock) {          // JDK 21: pin 住，丧失协程优势
    socket.read(buf);          // 建议换成 ReentrantLock
}

ReentrantLock l = new ReentrantLock();
l.lock();                      // JDK 21: 可以正常 unmount
try { socket.read(buf); } finally { l.unlock(); }
```

JDK 24（JEP 491）已解决 `synchronized` 导致的 pinning 问题。

---

## 六、总结对照表

### 暂停/恢复机制对照

| 环节 | Python | Go | Java |
|------|--------|-----|------|
| 谁判断该暂停 | **你写 `await`** | 运行时（阻塞调用 + 抢占信号） | JDK（阻塞 API 内部） |
| 现场存哪 | 协程对象的 `cr_frame` | `g.sched` + 栈拷贝到堆 | `StackChunk`（堆对象） |
| 恢复方式 | `coro.send()` 重新执行帧 | 汇编 `gogo` 恢复 SP/PC | `Continuation.run()` thaw |
| 自动让出 | ❌ 必须显式 | ✅ 全自动 | ✅ 全自动 |
| 多核并行 | ❌ 单线程事件循环 | ✅ GMP 调度 | ✅ 载体线程池 |

### 选型建议

| 场景 | 推荐 |
|------|------|
| Python 生态内的 Web 服务、爬虫、I/O 密集 | `asyncio` + `aiohttp` / `httpx` / FastAPI |
| 需要百万级连接、极致并发的后端服务 | Go（goroutine + channel） |
| 已有大量 Java 同步代码，想低成本提升并发 | Java 21+ 虚拟线程（代码零改造） |
| CPU 密集计算 | 多进程（Python）/ goroutine（Go）/ 平台线程或虚拟线程（Java） |

### 终极概括

> **Python** 把"暂停点"交给程序员用 `await` 标注——显式、轻量、单线程；
> **Go** 把暂停点交给编译器和运行时——`go` 关键字一键并发，2KB 栈起步，抢占式调度，真多核；
> **Java** 把暂停点交给 JDK 的阻塞 API——普通阻塞代码自动变协程，存量代码零改造。
>
> 三者都在解决同一个问题：**让等待 I/O 的时间不被浪费**。区别只在于——**谁来替你按下暂停键**。
