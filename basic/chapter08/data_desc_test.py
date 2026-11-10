class Dog:
    def speak(self):
        return "汪汪"

d = Dog()
print(d.__dict__)
d.speak = lambda: "喵喵"        # ① 实例级：只影响 d 这一个对象
print(d.speak())                # 喵喵
print(d.__dict__)
print(Dog().speak())            # 汪汪（其他实例不受影响）

def speak_new(self):
    return "嗷呜"
Dog.speak = speak_new           # ② 类级：影响所有实例
print(Dog().speak())            # 嗷呜
print(d.speak())                # 喵喵（实例字典优先，d 的覆盖还在）

import time
time.sleep = lambda s: print("假装睡了", s, "秒")   # ③ 模块级：连标准库都能换
time.sleep(2)                   # 假装睡了 2 秒（立即返回）