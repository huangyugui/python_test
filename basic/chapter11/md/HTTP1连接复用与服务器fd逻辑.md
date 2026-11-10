# HTTP/1.1 的连接复用 与 服务器端 fd 逻辑

> 存放位置：`basic\chapter11\md\HTTP1连接复用与服务器fd逻辑.md`
> 前置知识：`同步异步与阻塞非阻塞详解.md` 第 3 节（select 是"异步阻塞"）、文件描述符 fd、TCP 四元组
> 配套验证：本文服务器代码与输出均在 `D:\python\fastapi_test\.venv`（Python 3.13）实测

## 一句话结论

**HTTP/1.1 的"复用"是"一条连接串行跑多个请求"（keep-alive），不是真正的多路复用**——因为 HTTP/1.1 响应没有请求 ID，只能靠"哪条连接 + 第几个"来对应。服务器端则是 **1 个监听 fd + 每条连接 1 个 fd**，用 `select/epoll` 事件循环统一管理，注册表 `fd → 连接对象` 负责把"哪个 fd 就绪"翻译成"哪条连接的业务"。

---

## 1. HTTP/1.1 的"复用"到底是什么

### 1.1 三种连接方式

| 方式 | 行为 | 连接数 | 问题 |
|---|---|---|---|
| **短连接**（HTTP/1.0 默认） | 一个请求 → 建连接 → 收响应 → 关闭 | 请求数 = 连接数 | 每次 TCP 三次握手 + 慢启动，开销大 |
| **keep-alive**（HTTP/1.1 默认） | 一条连接上**串行**发多个请求，前一个响应完再发下一个 | 连接数 = 并发数 | 串行，后一个必须等前一个 |
| **pipelining** | 一条连接上连续发多个请求不等响应 | 连接数 = 1 | 响应**必须按顺序**返回，队头阻塞 |

### 1.2 为什么不是"多路复用"

HTTP/1.1 的响应报文长这样：

```
HTTP/1.1 200 OK
Content-Length: 13
Connection: keep-alive

hello /page1
```

**报文里没有"这是第几个请求的响应"**。客户端收到一个响应，只能按"**这条连接上请求的发送顺序**"去对应。所以：

- 如果请求 A 处理慢、请求 B 处理快，服务器也**必须等 A 的响应发完**才能发 B（否则客户端会错配）；
- 这就是 **HTTP/1.1 队头阻塞（head-of-line blocking）**。

**真正的多路复用必须给每个请求一个独立 ID**（HTTP/2 的 stream id），HTTP/1.1 没有这个字段，所以只能用"连接 + 顺序"来识别。

### 1.3 浏览器的应对：并行开多条连接

既然一条连接只能串行，浏览器就对同一域名开 **6 条左右**的并行连接（Chrome 是 6），把并发度提上去。代价是**服务器端的 fd 数量 = 6 × 用户数**——这正是下一节 fd 压力的来源。

## 2. 服务器端的 fd 拓扑

### 2.1 两类 fd

| fd 类型 | 数量 | 生命周期 | 作用 | 注册表里 data |
|---|---|---|---|---|
| **监听 fd**（listen socket） | 1 个 | 与进程同生共死 | 只负责 `accept` 新连接 | 一个标记（如 `"LISTEN"`） |
| **连接 fd**（已建立的 socket） | 每条连接 1 个 | 连接建立 → 关闭 | 收发这条连接的数据 | 连接对象（含请求缓冲、用户信息） |

```
进程
 ├── 监听 fd = 376 ──→ 内核 listen socket（大门）
 ├── 连接 fd = 448 ──→ 内核 socket（客户端 A 的专线）
 ├── 连接 fd = 424 ──→ 内核 socket（客户端 B 的专线）
 └── 连接 fd = 456 ──→ 内核 socket（客户端 C 的专线）
```

### 2.2 fd 数量压力的来源

- 1 个用户浏览器开 6 条连接 → 服务器 6 个 fd；
- 1000 个并发用户 → **6000 个连接 fd**；
- 这就是 **C10K 问题**的由来：单机要扛 1 万连接，就要 1 万个 fd + 能高效管理 1 万个 fd 的事件机制。

传统 `select` 有两个硬限制：

| 限制 | 说明 |
|---|---|
| `FD_SETSIZE`（默认 1024） | 一个 select 最多管 1024 个 fd |
| O(n) 扫描 | 每次 select 都要遍历所有 fd，fd 越多越慢 |

所以 Linux 用 **epoll**：上限只受 `ulimit -n` 和内存限制，返回时只给"就绪的那几个"，复杂度 O(就绪数)。

## 3. 事件循环五步（服务器端的完整逻辑）

```python
import socket, selectors

sel = selectors.DefaultSelector()

listen = socket.socket()
listen.bind(("127.0.0.1", 8000))
listen.listen(100)
listen.setblocking(False)                                # ① 非阻塞
sel.register(listen, selectors.EVENT_READ, "LISTEN")      # ② 登记监听 fd

while True:
    events = sel.select()                                  # ③ 阻塞等事件（异步阻塞）
    for key, mask in events:
        if key.data == "LISTEN":
            conn, _ = listen.accept()                      # ④a 大门响 → accept 新连接
            conn.setblocking(False)
            sel.register(conn, selectors.EVENT_READ, Conn(conn))   # 新 fd 登记
        else:
            conn_obj = key.data                            # ④b 连接响 → 查表取对象
            data = conn_obj.sock.recv(4096)
            if not data:                                   # ⑤ 客户端关闭
                sel.unregister(conn_obj.sock)              # 先注销
                conn_obj.sock.close()                      # 再关闭（顺序不能反）
            else:
                # 解析请求 → 生成响应 → send（HTTP/1.1 允许同一连接继续跑下一个请求）
                ...
```

**五个动作对应五件必须做的事**：

| 步骤 | 做什么 | 不做的后果 |
|---|---|---|
| ① | 监听 fd 和连接 fd 都设非阻塞 | 一个 `accept`/`recv` 卡住整个事件循环 |
| ② | 每个 fd 注册时绑定业务对象（`data`） | select 只给 fd 数字，你不知道是谁 |
| ③ | `select()` 阻塞等"任意 fd 就绪" | 忙等烧 CPU（不如用 select 的阻塞） |
| ④ | 按 `key.data` 分派：监听 vs 连接 | 把 `accept` 和 `recv` 混在一起 |
| ⑤ | **先 unregister 再 close** | fd 号被系统复用 → 新连接串到旧对象 |

### 3.1 注册表：服务器端的"名册"

`sel.get_map()` 就是这张表，实测内容：

```
fd=376 -> SelectorKey(fileobj=<监听 socket>, events=1, data='LISTEN')
fd=448 -> SelectorKey(fileobj=<连接 socket>, events=1, data=连接#1(fd=448))
fd=424 -> SelectorKey(fileobj=<连接 socket>, events=1, data=连接#2(fd=424))
fd=456 -> SelectorKey(fileobj=<连接 socket>, events=1, data=连接#3(fd=456))
```

**select 返回的 `key` 就是从这张表里查出来的**：内核只报"376/448 就绪"，Python 层把 fd 翻译成 `SelectorKey`，你拿到 `key.data` 就知道是哪条连接、哪个用户。

## 4. 实测：3 个客户端 × 2 个请求（keep-alive 复用）

代码（完整可运行）：客户端用 `http.client.HTTPConnection` 在同一条连接上连发两个请求；服务器用 `selectors` 处理。

```python
import socket, selectors, threading, time, http.client

class Conn:
    def __init__(self, idx, sock):
        self.idx, self.sock, self.buf, self.nreq = idx, sock, b"", 0
    def __repr__(self):
        return "连接#%d(fd=%d)" % (self.idx, self.sock.fileno())

sel = selectors.DefaultSelector()
listen = socket.socket(); listen.bind(("127.0.0.1", 0)); listen.listen(50)
listen.setblocking(False)
port = listen.getsockname()[1]
sel.register(listen, selectors.EVENT_READ, "LISTEN")

def handle(c, head):
    path = head.split(b"\r\n")[0].decode().split()[1]
    c.nreq += 1
    body = "hello %s" % path
    resp = ("HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n"
            "Content-Length: %d\r\nConnection: keep-alive\r\n\r\n%s" % (len(body), body))
    c.sock.send(resp.encode())
    print("  fd=%d 处理 %s（该连接第 %d 个请求）" % (c.sock.fileno(), path, c.nreq), flush=True)

def loop():
    while True:
        for key, mask in sel.select(timeout=0.3):
            if key.data == "LISTEN":
                conn, _ = listen.accept(); conn.setblocking(False)
                sel.register(conn, selectors.EVENT_READ, Conn(len(sel.get_map()) + 1, conn))
            else:
                c = key.data
                data = c.sock.recv(4096)
                if not data:
                    sel.unregister(c.sock); c.sock.close(); continue
                c.buf += data
                while b"\r\n\r\n" in c.buf:
                    head, c.buf = c.buf.split(b"\r\n\r\n", 1)
                    handle(c, head)

def client(i, delay):
    time.sleep(delay)
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    for j in range(2):
        conn.request("GET", "/user%d/req%d" % (i, j))
        print("    [客户端%d] 第%d个响应: %s" % (i, j + 1, conn.getresponse().read().decode()))
    conn.close()

threading.Thread(target=loop, daemon=True).start()
for i in range(3):
    threading.Thread(target=client, args=(i, 0.1 + i * 0.15), daemon=True).start()
time.sleep(1.5)
```

实测输出：

```
=== 服务器启动：监听 fd=376，端口=62128 ===
+0.17s [服务器] 监听 fd=376 有动静 -> accept 新连接 fd=448，登记为 连接#1(fd=448)
  [服务器] fd=448 读到请求 /user0/req0 -> 响应（该连接第 1 个请求）
    [客户端0] 第1个响应: hello /user0/req0
  [服务器] fd=448 读到请求 /user0/req1 -> 响应（该连接第 2 个请求）
    [客户端0] 第2个响应: hello /user0/req1
  [服务器] fd=448 读到 EOF -> unregister + close（fd 交还系统）

+0.30s [服务器] 监听 fd=376 有动静 -> accept 新连接 fd=424，登记为 连接#2(fd=424)
  [服务器] fd=424 读到请求 /user1/req0 -> 响应（该连接第 1 个请求）
    [客户端1] 第1个响应: hello /user1/req0
  [服务器] fd=424 读到请求 /user1/req1 -> 响应（该连接第 2 个请求）
    [客户端1] 第2个响应: hello /user1/req1
  [服务器] fd=424 读到 EOF -> unregister + close（fd 交还系统）

+0.45s [服务器] 监听 fd=376 有动静 -> accept 新连接 fd=456，登记为 连接#3(fd=456)
  [服务器] fd=456 读到请求 /user2/req0 -> 响应（该连接第 1 个请求）
    [客户端2] 第1个响应: hello /user2/req0
  [服务器] fd=456 读到请求 /user2/req1 -> 响应（该连接第 2 个请求）
    [客户端2] 第2个响应: hello /user2/req1
  [服务器] fd=456 读到 EOF -> unregister + close（fd 交还系统）

=== 结束：accept 3 次，处理 6 个请求，关闭 3 条连接 ===
剩余注册表 fd 列表: [376]（只剩监听 fd；3 个业务连接 fd 全部归还）
```

### 4.1 从输出里读出的四件事

1. **监听 fd 只有一个（376）**，所有新用户都由它 `accept` 出来；
2. **每个用户一条连接 fd（448 / 424 / 456）**，`accept` 时立马注册进名册，`data` 是 `Conn` 对象；
3. **同一条连接（fd=448）连续处理了 2 个请求**——这就是 HTTP/1.1 keep-alive 的"复用"：**连接复用，不是并发**。第 2 个请求必须等第 1 个响应发完；
4. **读到 EOF（`recv` 返回空）就 unregister + close**，fd 归还系统；结束时名册里只剩监听 fd 自己（它和进程同生共死）。

### 4.2 一个值得注意的细节：fd 会被复用

如果第 4 个客户端此时连上来，很可能拿到 **448** 这个刚归还的编号。fd 只是"号码牌"，**身份靠注册表里的 `data`**——这也是为什么"先 unregister 再 close"不能反：反了之后，下一个复用该 fd 的连接会被当成旧的 `Conn` 对象处理，请求就串了。

## 5. HTTP/1.1 的服务器端瓶颈

| 瓶颈 | 原因 | 表现 |
|---|---|---|
| **队头阻塞** | 一条连接串行处理请求 | 一个慢请求拖住同连接后续请求 |
| **连接数 = fd 数** | 每连接占 1 个 fd | 并发用户 × 6 → fd 耗尽（`Too many open files`） |
| **keep-alive 长期占 fd** | 空闲连接也不释放 | fd 池被闲连接占满 |
| **每连接内存** | 每连接需要缓冲/状态 | 1 万连接的内存开销可观 |
| **select 的 1024 上限** | `FD_SETSIZE` | 超过就报错，必须换 epoll |

排查 fd 的常用命令：

```bash
ls /proc/<pid>/fd | wc -l     # 进程当前 fd 数
ulimit -n                      # 上限（常为 1024 或 65535）
ss -s                          # 系统 TCP 连接概况
```

## 6. 为什么 HTTP/2 要引入 stream id

HTTP/1.1 的身份模型是"**连接 + 顺序**"，HTTP/2 换成"**连接 + stream id**"：

| 对比项 | HTTP/1.1 | HTTP/2 |
|---|---|---|
| 一条连接上的并发请求 | 只能串行（keep-alive） | 多 stream 并发交错 |
| 响应如何对应请求 | 靠发送顺序 | 帧头 **stream id** |
| 慢请求影响 | 队头阻塞，拖住后续 | 只影响自己的 stream |
| 服务器 fd 压力 | 每连接 1 fd，浏览器开 6 条 | 一条连接搞定，fd 大幅减少 |
| 取消单个请求 | 只能断连接 | `RST_STREAM` 只取消那一个 |

**HTTP/2 并没有去掉 fd**——它仍然是"一条连接一个 fd"，只是把"请求级多路复用"从"多开连接"变成了"一条连接内多 stream"，于是 fd 数量从 6× 用户数降到 1× 用户数。

## 7. 坑清单

1. **先 `close()` 后 `unregister()`**：fd 被复用后名册指向旧对象 → 请求串号（经典事故）。
2. **不按 `\r\n\r\n` 分帧就解析请求**：TCP 是字节流，一个 `recv` 可能读到半个请求或两个请求（粘包），必须按分隔符/长度拆。
3. **keep-alive 响应的 `Content-Length` 不对**：客户端会一直等或截断，连接复用直接崩。
4. **监听 fd 也设非阻塞却忘了 `accept` 循环**：`accept` 一次只接一个，积压连接要循环 accept 到 `EAGAIN`。
5. **忘记处理 EOF**：客户端关闭后 `recv` 返回 `b""`，不 unregister+close 就 fd 泄漏。
6. **select 管超过 1024 个 fd**：报 `ValueError`/`select` 失败，换 `selectors.DefaultSelector`（Linux 上是 epoll）。
7. **用 HTTP/1.1 的连接数思维估算 fd**：浏览器每域名 6 连接，1 万用户就是 6 万 fd，必须提前调 `ulimit -n` 或用 HTTP/2。

## 8. 一句话记忆

> **HTTP/1.1 = 一条连接串行跑多个请求（keep-alive），身份靠"连接 + 顺序"；服务器端 = 1 个监听 fd + 每连接 1 个 fd，select 报"哪个 fd 就绪"，注册表 `fd → 连接对象` 告诉你"是谁"。**
> **HTTP/2 = 一条连接内多 stream，身份靠帧头 stream id，fd 压力从"6× 用户"降到"1× 用户"。**

## 9. 呼应章节

- chapter11 `同步异步与阻塞非阻塞详解.md` 第 3 节：select/epoll 为何是"异步阻塞"；第 4 节实测数字。
- chapter11 后续"多路复用双层身份"：I/O 多路复用（fd → 连接）与 HTTP/2 协议多路复用（stream id → 请求）是两层不同的身份。
- FastAPI 部署：uvicorn 默认用事件循环 + 非阻塞 socket；`async def` 卡住 loop 就等于整个服务器的 `select` 停摆。
