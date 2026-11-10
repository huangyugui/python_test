class Date:
    def __init__(self, year, month, day):
        self.year, self.month, self.day = year, month, day

    # classmethod：工厂方法，用 cls 构造，子类调用时返回子类实例
    @classmethod
    def from_str(cls, s):
        y, m, d = map(int, s.split('-'))
        return cls(y, m, d)

    # staticmethod：纯工具函数，不依赖 cls / self
    @staticmethod
    def is_valid(s):
        try:
            y, m, d = map(int, s.split('-'))
            return 1 <= m <= 12 and 1 <= d <= 31
        except ValueError:
            return False

    def __str__(self):
        return "Date"


class MyDate(Date):
    def __str__(self):
        return "MyDate"


if __name__ == '__main__':
    d1 = Date.from_str('2026-10-25')  # cls = Date     → Date 实例
    d2 = MyDate.from_str('2026-10-25')  # cls = MyDate   → MyDate 实例（多态！）
    d3 = Date(2026, 10, 25)  # 普通构造

    print(type(d2))
    print(d1)
    print(d2)

    print(Date.is_valid('2026-10-25'))  # True   不依赖任何实例/类状态
