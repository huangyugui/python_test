def testTry():
    try:
        print("do something")
        # raise RuntimeError
    except RuntimeError as e:
        print("runtime error")
    else:  # 没有异常时执行
        print("other error")
    finally:
        print("finally")

class EnterTest:
    def __enter__(self):
        print("enter")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("exit")

    def do_something(self):
        print("do something")

from contextlib import contextmanager
from datetime import datetime
@contextmanager
def contextmanagerTest():
    print("enter")
    yield datetime.today()
    print("exit")


if __name__ == '__main__':
    testTry()

    print("-" * 20)
    with EnterTest() as ent:
        ent.do_something()

    print("-" * 20)
    with contextmanagerTest() as ent1:
        print(f"今天的日期是:{ent1.day}")
        print("do something")

