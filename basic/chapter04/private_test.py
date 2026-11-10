class Date:
    def __init__(self, day, month, year):
        self.day = day
        self.month = month
        self.year = year

    def __str__(self):
        return f'{self.day} {self.month} {self.year}'

class Student:
    def __init__(self, name, birthday):
        self._name = name
        # 私有属性
        self.__birthday = birthday

    def _getName(self):
        return self._name

    # 私有方法
    def __getName1(self):
        return self._name


    def getAge(self):
        from datetime import datetime
        return datetime.today().year - self.__birthday.year


# 维度	    _x 单下划线	            __x 双下划线
# 性质	    命名约定（PEP 8 惯例）	    名称改写（语法机制）
# 外部访问	obj._x 直接可以	        obj.__x 报错；obj._类名__x 可以
# 子类同名	会覆盖（冲突）	            各带类名前缀，互不干扰
# import *	不导出（除非 __all__）	    不导出
# IDE 提示	"受保护成员" 警告	        "私有成员" 警告
# 真正的私有？	否	                    否（能绕过）
if __name__ == '__main__':
    s = Student("zhangsan", Date(12, 12, 2020))
    print(s._name)
    print(s._getName())

    # 私有属性和私有方法的访问方式
    print(s._Student__getName1())
    print(s._Student__birthday)