"""
I/O 多路复用（selectors 单线程）的 TCP 服务器
================================================

原理
----
1. 监听 socket 设为【非阻塞】。
2. 只有【一个线程】和一个 selectors 事件循环：
      注册表里放：监听 fd -> "LISTEN"，每个连接 fd -> Conn 对象
      每次 select() 阻塞等待"任意 fd 就绪"，返回就绪的 key 列表
      按 key.data 分派：监听 fd 就 accept；连接 fd 就 recv/send
3. 关键点：
   - select() 本身是阻塞的（等事件），但它一次等【所有】fd；
     所以 1 个线程就能同时管理成百上千条连接。
   - 每条连接的身份不在 fd 号里，而在【注册表的 data】里（Conn 对象）。
   - 任何 fd 上的 recv/send 都必须是非阻塞的，否则一个卡住就拖死整个循环。

和同步阻塞（sync_blocking_server.py）的区别
-------------------------------------------
- 本文件：1 个线程管全部连接；连接数增长不增加线程数，只增加注册的 fd 数。
- 另一版：1 连接 1 线程；连接数增长会线性增加线程数。

运行方式
--------
    python io_multiplexing_server.py

预期输出（5 个客户端，每个发 2 个请求）
--------------------------------------
    [事件循环] 监听 fd=...，单线程开始 select（select 自身是阻塞的）
    [事件循环] 新连接 -> 注册 fd=...，当前注册 fd 数 = 2
    ...
    [统计] accept 连接 5 条，处理请求 10 个，事件循环线程数 1，峰值注册 fd 数 6
"""

import socket
import selectors
import threading
import time
import http.client

HOST = "127.0.0.1"


class Conn:
    """一条连接的全部状态，作为注册表里的 data。"""

    def __init__(self, idx, sock):
        self.idx = idx
        self.sock = sock
        self.buf = b""
        self.nreq = 0

    def __repr__(self):
        return "连接#%d(fd=%d)" % (self.idx, self.sock.fileno())


class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.conns = 0
        self.served = 0
        self.peak_fds = 0
        self.stop = False

    def next_conn(self):
        with self.lock:
            self.conns += 1
            return self.conns

    def on_request(self):
        with self.lock:
            self.served += 1

    def update_peak(self, n):
        with self.lock:
            self.peak_fds = max(self.peak_fds, n)


def parse_path(data):
    try:
        first_line = data.decode("utf-8", errors="ignore").split("\r\n")[0]
        return first_line.split()[1]
    except Exception:
        return "/"


def handle_request(conn_obj, stats):
    """从缓冲区里取出一个完整请求（按 \\r\\n\\r\\n 分帧），立即响应（不阻塞）。"""
    head, conn_obj.buf = conn_obj.buf.split(b"\r\n\r\n", 1)
    path = parse_path(head)
    conn_obj.nreq += 1
    body = "hello %s" % path
    conn_obj.sock.send((
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: text/plain\r\n"
        "Content-Length: %d\r\n"
        "Connection: keep-alive\r\n"
        "\r\n%s" % (len(body), body)
    ).encode())
    stats.on_request()
    print("[事件循环] %s 处理 %s（该连接第 %d 个请求，单线程里非阻塞完成）"
          % (conn_obj, path, conn_obj.nreq), flush=True)


def event_loop(listen_sock, stats):
    """单线程事件循环：select 阻塞等事件，按 key.data 分派。"""
    sel = selectors.DefaultSelector()
    sel.register(listen_sock, selectors.EVENT_READ, "LISTEN")
    print("[事件循环] 监听 fd=%d，单线程开始 select（select 自身是阻塞的，但它一次等所有 fd）"
          % listen_sock.fileno(), flush=True)

    while not stats.stop:
        try:
            events = sel.select(timeout=0.2)      # ← 阻塞等待"任意 fd 就绪"
        except (OSError, ValueError):
            break
        for key, mask in events:
            if key.data == "LISTEN":
                # 监听 fd 就绪：可能有多个连接同时到来，要 accept 到没有为止
                while True:
                    try:
                        conn, addr = listen_sock.accept()
                    except BlockingIOError:
                        break
                    conn.setblocking(False)   # 连接 fd 必须非阻塞
                    c = Conn(stats.next_conn(), conn)
                    sel.register(conn, selectors.EVENT_READ, c)
                    stats.update_peak(len(sel.get_map()))
                    print("[事件循环] 新连接 %s -> 注册 fd=%d，当前注册 fd 数 = %d"
                          % (addr, conn.fileno(), len(sel.get_map())), flush=True)
            else:
                c = key.data
                try:
                    data = c.sock.recv(4096)  # 非阻塞：有数据就返回，没数据抛 BlockingIOError
                except BlockingIOError:
                    continue
                if not data:                  # 客户端关闭：先注销，再关闭
                    print("[事件循环] %s 读到 EOF -> unregister + close" % c, flush=True)
                    sel.unregister(c.sock)
                    c.sock.close()
                    continue
                c.buf += data
                while b"\r\n\r\n" in c.buf:
                    handle_request(c, stats)
    sel.close()


def demo():
    """自测：5 个客户端并发访问，每个发 2 个请求（keep-alive 复用连接）。"""
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, 0))
    server.listen(128)
    server.setblocking(False)                 # ← 监听 fd 非阻塞
    port = server.getsockname()[1]
    stats = Stats()

    loop_thread = threading.Thread(target=event_loop, args=(server, stats), daemon=True)
    loop_thread.start()
    time.sleep(0.05)

    t_start = time.perf_counter()

    def client(i):
        conn = http.client.HTTPConnection(HOST, port, timeout=5)
        for j in range(2):
            conn.request("GET", "/user%d/req%d" % (i, j))
            body = conn.getresponse().read().decode()
            print("    [客户端%d] 第%d个响应: %s" % (i, j + 1, body), flush=True)
        conn.close()

    clients = [threading.Thread(target=client, args=(i,)) for i in range(5)]
    for t in clients:
        t.start()
    for t in clients:
        t.join()

    stats.stop = True          # 通知事件循环退出（select 最多 0.2s 后返回并检查该标志）
    time.sleep(0.3)
    print()
    print("[统计] accept 连接 %d 条，处理请求 %d 个，事件循环线程数 1，峰值注册 fd 数 %d"
          % (stats.conns, stats.served, stats.peak_fds), flush=True)
    print("[统计] 总耗时 %.2fs（全部连接由同一个线程通过 select 事件分派处理）"
          % (time.perf_counter() - t_start), flush=True)
    server.close()


if __name__ == "__main__":
    demo()
