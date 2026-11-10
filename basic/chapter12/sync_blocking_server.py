"""
同步阻塞模型（每连接一个线程）的 TCP 服务器
================================================

原理
----
1. 监听 socket 用【阻塞模式】调用 accept()：
   没有新连接时，主线程被内核挂起，直到有人连进来。
2. 每 accept 到一个连接，就新建一个线程，由这个线程负责这条连接：
   线程里用【阻塞模式】调用 recv()，没有数据时该线程被挂起，
   但其他连接线程照常工作（阻塞只按住"当前线程"）。
3. 所以：连接数 = 处理线程数 = 被阻塞的线程数。
   1 万个连接就要 1 万个线程 —— 这就是同步阻塞模型的上限所在。

和 I/O 多路复用（io_multiplexing_server.py）的区别
--------------------------------------------------
- 本文件：1 连接 1 线程，靠"多开线程"实现并发；线程有栈和上下文切换成本。
- 另一版：1 个线程 + selectors 管理所有连接，靠"事件通知"实现并发。

运行方式
--------
    python sync_blocking_server.py

预期输出（5 个客户端，每个发 2 个请求）
--------------------------------------
    [监听] 阻塞 accept 中（主线程会被挂起）
    [连接#1] ('127.0.0.1', xxxxx) 建立 -> 处理线程 Thread-2（该线程随后会被 recv 阻塞）
    ...
    [统计] accept 连接 5 条，处理请求 10 个，服务器侧峰值线程数 6（1 个 accept 线程 + 5 个连接线程）
    [统计] 总耗时 0.3xs（每个连接一个线程，线程间并行；但每个线程内部是同步阻塞的）
"""

import socket
import threading
import time
import http.client

HOST = "127.0.0.1"


class Stats:
    """简单的计数器（线程安全）。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.conns = 0
        self.served = 0
        self.active = 0
        self.peak_conn_threads = 0

    def next_conn(self):
        with self.lock:
            self.conns += 1
            self.active += 1
            # 只统计"连接线程"的峰值；accept 线程恒为 1，demo 客户端线程不计入
            self.peak_conn_threads = max(self.peak_conn_threads, self.active)
            return self.conns

    def on_request(self):
        with self.lock:
            self.served += 1

    def on_close(self):
        with self.lock:
            self.active -= 1


def parse_path(data):
    """从一行 HTTP 请求里解析出路径；解析失败就返回 '/'。"""
    try:
        first_line = data.decode("utf-8", errors="ignore").split("\r\n")[0]
        return first_line.split()[1]
    except Exception:
        return "/"


def handle_conn(conn, addr, stats):
    """一条连接一个线程：这里用阻塞 recv，线程会被内核挂起。"""
    conn_id = stats.next_conn()
    thread_name = threading.current_thread().name
    print("[连接#%d] %s 建立 -> 处理线程 %s（该线程随后会被 recv 阻塞）"
          % (conn_id, addr, thread_name), flush=True)
    try:
        while True:
            data = conn.recv(4096)              # ← 阻塞点：无数据时本线程被挂起
            if not data:                        # 客户端关闭 -> recv 返回 b""
                print("[连接#%d] %s 关闭，线程 %s 结束" % (conn_id, addr, thread_name), flush=True)
                break

            path = parse_path(data)
            body = "hello %s" % path
            conn.send((
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/plain\r\n"
                "Content-Length: %d\r\n"
                "Connection: keep-alive\r\n"
                "\r\n%s" % (len(body), body)
            ).encode())
            stats.on_request()
            print("[连接#%d] 线程 %s 处理 %s -> 响应（同步阻塞线程里顺序执行）"
                  % (conn_id, thread_name, path), flush=True)
    except OSError as e:
        print("[连接#%d] 异常：%s" % (conn_id, e), flush=True)
    finally:
        conn.close()
        stats.on_close()


def serve(listen_sock, stats):
    """阻塞 accept 循环：没有新连接时，主线程挂起在 accept() 上。"""
    print("[监听] fd=%d 阻塞 accept 中（主线程会被挂起）" % listen_sock.fileno(), flush=True)
    while True:
        try:
            conn, addr = listen_sock.accept()   # ← 阻塞点：无新连接时主线程挂起
        except OSError:
            break
        t = threading.Thread(target=handle_conn, args=(conn, addr, stats), daemon=True)
        t.start()


def demo():
    """自测：5 个客户端并发访问，每个发 2 个请求（keep-alive 复用连接）。"""
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, 0))
    server.listen(128)
    # 注意：这里【不】设置非阻塞，保持默认阻塞模式
    port = server.getsockname()[1]
    stats = Stats()

    accept_thread = threading.Thread(target=serve, args=(server, stats), daemon=True)
    accept_thread.start()
    time.sleep(0.05)

    t_start = time.perf_counter()

    barrier = threading.Barrier(5)   # 让 5 条连接先全部建立，再统一发请求

    def client(i):
        conn = http.client.HTTPConnection(HOST, port, timeout=5)
        conn.connect()               # 先建立 TCP 连接（服务器会 accept 并起一个线程）
        barrier.wait()               # 等 5 条连接都在了
        time.sleep(0.1)              # 留一点时间让服务器的 accept 循环把 5 条全接完
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

    time.sleep(0.2)
    print()
    print("[统计] accept 连接 %d 条，处理请求 %d 个，服务器侧峰值线程数 %d（1 个 accept 线程 + %d 个连接线程）"
          % (stats.conns, stats.served, stats.peak_conn_threads + 1, stats.peak_conn_threads), flush=True)
    print("[统计] 总耗时 %.2fs（每个连接一个线程，线程间并行；但每个线程内部是同步阻塞的）"
          % (time.perf_counter() - t_start), flush=True)
    server.close()


if __name__ == "__main__":
    demo()
