class Field:
    """描述符：管属性读写的校验"""
    def __init__(self, dtype, required=False):
        self.dtype = dtype
        self.required = required
        self.storage_name = None           # 由元类回填

    def __set__(self, obj, value):
        if not isinstance(value, self.dtype):
            raise TypeError(f"{self.storage_name} 需要 {self.dtype.__name__}")
        obj.__dict__[self.storage_name] = value

    def __get__(self, obj, owner):
        if obj is None:
            return self
        return obj.__dict__.get(self.storage_name)

class ModelMeta(type):
    def __new__(mcls, name, bases, ns):
        fields = {}
        for base in bases:                 # 先继承父类已收集的字段
            fields.update(getattr(base, "_fields", {}))
        for key, val in ns.items():        # 再收集本类新声明的字段
            if isinstance(val, Field):
                val.storage_name = key     # 回填字段名给描述符用
                fields[key] = val
        cls = super().__new__(mcls, name, bases, ns)
        cls._fields = fields
        return cls

class Model(metaclass=ModelMeta):
    def __init__(self, **kwargs):
        missing = [f for f, spec in self._fields.items()
                   if spec.required and f not in kwargs]
        if missing:
            raise TypeError(f"缺少必填字段: {missing}")
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        return {k: getattr(self, k) for k in self._fields}

class User(Model):
    name = Field(str, required=True)
    age = Field(int)

if __name__ == '__main__':
    u = User(name="Tom", age=18)
    print(u.to_dict())            # {'name': 'Tom', 'age': 18}
    User(name=123)                # TypeError: name 需要 str
    User(age=1)                   # TypeError: 缺少必填字段: ['name']