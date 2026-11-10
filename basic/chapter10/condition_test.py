import threading
import time

cond = threading.Condition()
buffer = []
MAX = 5

def producer():
    count = 1
    while True:
        with cond:
            while len(buffer) == MAX:
                cond.wait()
            buffer.append(f"馒头{count}")
            print(f"生产了--->>> 馒头{count}")
            time.sleep(0.5)  # 模拟消费耗时
            count += 1
            cond.notify_all()

def consumer():
    while True:
        with cond:
            while not buffer:
                cond.wait()
            print(f"消费了---<<<{buffer.pop()}, 库存：{len(buffer)}")
            time.sleep(0.5)
            cond.notify_all()


if __name__ == '__main__':
        producer1 = threading.Thread(target=producer)
        producer1.start()

        consumer1 = threading.Thread(target=consumer)
        consumer2 = threading.Thread(target=consumer)
        consumer1.start()
        consumer2.start()

        producer1.join()
        consumer1.join()
        consumer2.join()