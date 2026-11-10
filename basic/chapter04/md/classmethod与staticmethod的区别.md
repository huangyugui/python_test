# @classmethod 与 @staticmethod 的区别与使用场景

> 章节：chapter04 · Python 类方法机制
> 与 chapter01 的关系：`type(x)` 精确类型 / `isinstance(x, T)` 继承链检查，类视角见 `__bases__` / `__mro__`；本章讨论类内部三种方法形态的绑定机制。

## 一句话结论

- **`@staticmethod`**：不带任何隐式参数，就是一个**放进类命名空间的普通函数**——不绑定实例（self），也不绑定类（cls），内部无法访问类属性/实例属性（除非显式传入）。
- **`@classmethod`**：第一个参数 **`cls` 自动绑定"调用者所在的类"**——通过类调用绑定该类，通过子类调用绑定**子类**。因此它可以访问类属性、调用其他类方法，且天然支持"多态工厂"。

> 记忆：`staticmethod` 是"借了类的外壳的函数"，`classmethod` 是"绑定到类（及子类）的方法"。

---

## 1. 机制核心：绑定差异

| 形态 | 隐式参数 | 绑定对象 | 能否访问类属性 | 能否访问实例属性 |
|---|---|---|---|---|
| 实例方法 | `self` | 实例 | 通过 `self.__class__` 间接 | 能 |
| `@classmethod` | `cls` | **调用者所在的类**（子类调用=子类） | 能（`cls.x`） | 不能（无 self） |
| `@staticmethod` | 无 | 无 | 不能（除非显式传类） | 不能（除非显式传实例） |

关键点：`classmethod` 的 `cls` **跟随调用者**——这是它与 `staticmethod` 在继承场景下行为分化的根源。

## 2. 代码示例

```python
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


class MyDate(Date):
    pass


d1 = Date.from_str('2026-10-25')     # cls = Date     → Date 实例
d2 = MyDate.from_str('2026-10-25')   # cls = MyDate   → MyDate 实例（多态！）
d3 = Date(2026, 10, 25)              # 普通构造

Date.is_valid('2026-10-25')          # True   不依赖任何实例/类状态
```

核心差异演示：同一个 `from_str`，`Date` 调用产出 `Date`，`MyDate` 调用产出 `MyDate`——这就是 `cls` 跟随调用者的多态构造。

## 3. 行为对比表

| 对比维度 | `@staticmethod` | `@classmethod` |
|---|---|---|
| 隐式参数 | 无 | `cls`（调用者所在的类） |
| 本质 | 类命名空间里的普通函数 | 绑定类的方法（descriptor） |
| 类调用 | `Date.is_valid(s)` | `Date.from_str(s)` → cls=Date |
| 子类调用 | 行为不变 | cls=**子类**（多态） |
| 实例调用 | `d.is_valid(s)` 可行，无绑定 | `d.from_str(s)` 可行，cls 仍是**类**而非实例 |
| 访问类属性 | 不可（除非显式传） | 可（`cls.x`） |
| 访问实例属性 | 不可 | 不可 |
| 与 `@abstractmethod` 组合 | 可以（纯抽象校验） | 可以（类级抽象工厂） |
| 典型用途 | 工具/校验/纯函数 | 工厂方法/访问类级状态/多态构造 |

注意：实例调用 `classmethod` 时，`cls` 依然是类，**不是实例**——`cls` 永远绑定类。

## 4. 使用场景

### 4.1 @classmethod —— 需要"类"参与的场合

1. **工厂方法（替代/补充 `__init__`）**：一个类有多个构造入口时，用 classmethod 提供命名构造器。
   ```python
   user = User.from_json(raw_json)
   cfg = Config.from_env()
   ```
2. **多态构造（依赖继承）**：基类定义工厂，子类继承后调用，自动产出子类实例——ORM 模型、序列化框架的通用模式。
   ```python
   class BaseModel:
       @classmethod
       def get(cls, pk):            # Django/Peewee 风格的查询入口
           return cls._table.get(pk)   # 返回 cls 的实例
   ```
3. **访问/修改类级状态**：类变量计数器、全局注册表、连接池、类级缓存。
   ```python
   class Registry:
       _items = {}
       @classmethod
       def register(cls, name, obj):
           cls._items[name] = obj      # 读写类属性
   ```
4. **类级抽象接口**：与 `@abstractmethod` 组合，定义"每个子类都必须实现"的类方法契约。

### 4.2 @staticmethod —— 不需要"类"参与的场合

1. **纯工具/校验函数**：逻辑与类相关，但不需要类状态和实例状态。
   ```python
   class Date:
       @staticmethod
       def is_valid(s): ...     # 校验逻辑
   ```
2. **单位换算 / 格式化 / 辅助计算**：`Math` 风格的工具方法集合。
   ```python
   class Price:
       @staticmethod
       def to_fen(yuan):
           return int(round(yuan * 100))
   ```
3. **组织代码命名空间**：把一组相关纯函数放进类里，只为了可读性和调用语义（`StringUtil.trim()` 而非模块级 `trim()`），此时不需要 cls。

### 4.3 判断口诀

- 函数体内需要 **`cls` / 类属性 / 子类多态** → `@classmethod`
- 函数体内既不需要 `cls` 也不需要 `self`，参数全显式 → `@staticmethod`
- 需要 `self` / 实例属性 → 普通实例方法

## 5. 常见坑

1. **在 staticmethod 里访问类属性**：`AttributeError` 或拿到的是全局变量，必须显式把类传进来（`Date.is_valid` 内部拿不到 `Date` 的任何状态）。
2. **classmethod 里访问实例属性**：没有 self，编译不过/语义错误；需要实例数据就把实例作为显式参数传入。
3. **实例调用 classmethod**：`d.from_str(...)` 里 cls 仍然是类，不是 `d`，别指望拿到实例状态。
4. **把 staticmethod 当 classmethod 用**：想"在子类里拿到子类"时 staticmethod 做不到——它不感知继承，这正是多态工厂必须用 classmethod 的原因。
5. **性能差异**：staticmethod 少一次绑定，微秒级差距，可忽略；选型只看语义，不看性能。

## 6. 与 FastAPI 项目的关联

FastAPI 依赖注入、Pydantic 模型中常见的两种用法：

- **Pydantic v2 `model_validate` / `model_construct`**：本质是 classmethod 风格的多态构造器。
- **校验器 `@field_validator`（默认类方法模式）**：接收 `cls` 参数，用于跨字段校验——是 classmethod 语义在框架内的典型体现。

写作本文时不必深挖框架源码，先掌握绑定机制，再对照框架用法即可。
