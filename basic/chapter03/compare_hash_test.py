from basic.chapter02.my_student import Student

class HashTest():
    def __init__(self, userId):
        self.userId = userId

    def __eq__(self, other):
        return self.userId == other.userId

    def __hash__(self):
        return hash(self.userId)


# - 你**没重写** `__eq__`（保持默认按地址比较）→ 哈希也默认，啥都不用做
# - 你重写了 `__eq__`，但**不需要**把对象放集合 / 字典 → 不用管，报错就报错（`in [list]`、`==` 判断都不受影响）
# - 你重写了 `__eq__` 且对象**不可变**（如 `frozenset`、`tuple` 场景）→ 可以放心手动实现 `__hash__`；如果是可变对象进集合，改了属性哈希值会变，容易出隐蔽 bug
u1, u2, u3 = HashTest("u1"), HashTest("u2"), HashTest("u3")
set1 = {u1, u2, u3}