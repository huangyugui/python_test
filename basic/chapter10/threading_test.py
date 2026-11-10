import threading

def worker(name):
    print(f"worker_{name}")


class MyThread(threading.Thread):
    def __init__(self, name, index):
        self._name = name
        self.index = index
        super().__init__()

    def run(self):
        print(f"worker_{self.index} start")

if __name__ == '__main__':
    for i in range(10):
        threading.Thread(target=worker, args=(i,), name=f"thread_{i}").start()

    for i in range(10):
        t = MyThread(name=f"thread_{i}", index=i)
        t.start()

