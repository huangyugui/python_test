import queue
import threading
import time

queue = queue.Queue()

def producer():
    count = 1
    while True:
        queue.put(count)
        print(f"生产了---》》》馒头{count}")
        time.sleep(0.5)
        count += 1

def consumer():
    while True:
        print(f"消费了---《《《馒头{queue.get()}")
        time.sleep(1)
        queue.task_done()


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