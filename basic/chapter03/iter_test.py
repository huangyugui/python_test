class IterTest:
    def __init__(self, start):
        self.start = start

    def __iter__(self):
        return self

    def __next__(self):
        if self.start < 10:
            self.start += 1
            return self.start
        else:
            raise StopIteration

for n in IterTest(0):
    print(n)
