class Company:
    def __init__(self, name, employees):
        self.name = name
        self.employees = employees

    # def __str__(self):
    #     return "companyName: {name}, employees: {employees}".format(name=self.name, employees=self.employees)

    def __repr__(self):
        return "repr: companyName: {name}, employees: {employees}".format(name=self.name, employees=self.employees)

    def __getitem__(self, item):
        return self.employees[item]

    def __enter__(self):
        print("进入")
        return self.employees

    def __exit__(self, exc_type, exc_val, exc_tb):
        # exc_type: 异常类型（没有异常为 None）
        # exc_val : 异常实例
        # exc_tb  : traceback 对象
        print("exc_type: {}, exc_val: {}, exc_tb: {}".format(exc_type, exc_val, exc_tb))
        if exc_type is None:
            self.employees.clear()
        return False

myCompany = Company(name="MyCompany", employees=["jone", "tom", "petter"])
print(myCompany)
myCompany
print(type(myCompany))

print("-------------------getitem----------------")
for employee in myCompany.employees:
    print(employee)

print("-------------------enter----------------")
with myCompany:
    print(myCompany)

print(myCompany)

print("-------------------demo.enter----------------")
class Demo:
    def __enter__(self):
        print("进入")
        return self
    def __exit__(self, *args):
        print("无论正常还是异常，都会走到这里")
        return False

# 场景1：正常结束
with Demo():
    print("执行中")

# 场景2：中途异常 —— __exit__ 依然执行，之后异常继续抛
try:
    with Demo():
        raise RuntimeError("出错了")
except RuntimeError as e:
    print("捕获到:", e)

# 进入
# 执行中
# 无论正常还是异常，都会走到这里
# 进入
# 无论正常还是异常，都会走到这里
# 捕获到: 出错了

