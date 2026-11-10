# Python 迭代器协议详解

> 围绕两个常见问题:① 可迭代对象与迭代器的区别;② `for` 循环调用的是 `__getitem__` 还是 `__iter__`。两者合起来是 Python"协议优先于类型"设计思想的一次完整呈现。

---

## 一、可迭代对象与迭代器的区别

### 1.1 一句话概括

**可迭代对象(Iterable)是"能被 `for` 遍历的东西",迭代器(Iterator)是"真正干活逐个吐出元素的东西"**。可迭代对象是数据的容器,迭代器是遍历这个容器的游标,两者是"容器"和"取数器"的关系。

### 1.2 协议层面的区别

- **可迭代对象**:实现了 `__iter__` 方法,调用它返回一个迭代器。列表、元组、字符串、字典、集合、文件对象都是。
- **迭代器**:同时实现了 `__iter__` 和 `__next__`。`__next__` 返回下一个元素,没有更多元素时抛 `StopIteration`。

`for` 循环背后就是这两步:先对目标调 `iter()` 拿到迭代器,再不断调 `next()` 直到 `StopIteration`:

```python
nums = [1, 2, 3]        # 可迭代对象,没有 __next__
it = iter(nums)         # 等价于 nums.__iter__(),拿到迭代器
next(it)                # 1
next(it)                # 2
next(it)                # 3
next(it)                # StopIteration —— for 循环就是靠捕获它来结束的
```

### 1.3 核心区别对比

| | 可迭代对象 | 迭代器 |
|---|---|---|
| 必须实现 | `__iter__` | `__iter__` + `__next__` |
| 有没有"当前位置" | 没有,只描述数据 | 有,记录遍历到哪了 |
| 能否重复遍历 | 通常可以(每次 `iter()` 给新迭代器) | 不能,是一次性的,耗尽即空 |
| `next()` 能否直接调用 | 不行 | 可以 |
| 典型例子 | `list`、`str`、`dict`、`range` | `zip`、`map`、`filter`、`enumerate` 返回值、生成器、文件对象 |

### 1.4 容易踩坑的点

**1. 迭代器本身也是可迭代对象。** 它的 `__iter__` 返回自己(`iter(it) is it`),所以迭代器可以直接放进 `for`。但反过来不成立——列表是可迭代对象却不是迭代器:

```python
from collections.abc import Iterable, Iterator

isinstance([1, 2], Iterable)        # True
isinstance([1, 2], Iterator)        # False
isinstance(iter([1, 2]), Iterator)  # True
```

**2. 迭代器是一次性的,列表不是。** 这是最常见的 bug 来源:

```python
nums = [1, 2, 3]
for x in nums: ...   # 遍历完
for x in nums: ...   # 还能再来一遍,列表没事

gen = (x for x in [1, 2, 3])   # 生成器是迭代器
for x in gen: ...              # 消耗完了
for x in gen: ...              # 第二遍为空!不报错,只是循环体一次都不执行
```

`map`、`zip`、`filter`、`enumerate` 的返回值和文件对象都一样是"读一次就没了"。想重复用就先 `list()` 落地,或者重新 `iter()`。

**3. 自定义时区分两种写法。** 只想做容器 → 只实现 `__iter__`;想自己控制取数过程 → 实现 `__next__`:

```python
# 只做可迭代对象:__iter__ 里 yield,简单最常用
class Countdown:
    def __init__(self, n): self.n = n
    def __iter__(self):
        while self.n > 0:
            yield self.n
            self.n -= 1

for x in Countdown(3): print(x)   # 3 2 1,可反复创建新实例重复遍历

# 完整迭代器:__iter__ 返回 self,__next__ 控制游标
class CountdownIterator:
    def __init__(self, n): self.n = n
    def __iter__(self): return self
    def __next__(self):
        if self.n <= 0:
            raise StopIteration
        self.n -= 1
        return self.n + 1
```

实际写代码时,用生成器函数(`yield`)几乎总是比手写 `__next__` 省事,因为生成器天生就是迭代器。

**4. 判断依据是行为,不是类型。** `iter(obj)` 成功 → 是可迭代对象;`next(obj)` 成功 → 是迭代器。duck typing 下自己实现对应魔法方法也算。

---

## 二、`for` 循环调用的是 `__getitem__` 还是 `__iter__`

**调用的是 `__iter__`,不会走 `__getitem__`**。`list` 定义了 `__iter__`,`for` 循环第一步就是调 `iter(lst)` 拿到 `list_iterator`,之后每次调 `next()` 推进,全程不涉及下标。

### 2.1 `for` 的完整规则

`for` 先调 `iter(对象)`,`iter()` 按**优先级**找东西:

1. **先找 `__iter__`** —— 找到就直接用它(迭代器协议),这是标准路径;
2. **找不到才退而求其次找 `__getitem__`** —— 如果类型只定义了 `__getitem__`,`iter()` 会自动造一个"旧式迭代器",从下标 0 开始调用 `obj[0], obj[1], ...`,直到抛 `IndexError` 为止。

也就是说 `__getitem__` 只是历史遗留的兼容路径(旧式序列协议),有了 `__iter__` 就轮不到它。

### 2.2 验证优先级

```python
class Demo:
    def __iter__(self):
        print("走了 __iter__")
        yield 1

    def __getitem__(self, i):
        print(f"走了 __getitem__ {i}")
        raise IndexError

for x in Demo():   # 只打印"走了 __iter__"
    pass

# 把 __iter__ 注释掉再跑,才会看到:__getitem__ 0, __getitem__ 1... 直到 IndexError
```

### 2.3 为什么迭代器协议更高效

`list_iterator` 是 C 层实现,内部直接顺着底层指针数组移动,不用每次做下标运算和整数装箱;如果走 `__getitem__` 路径,每次迭代都要构造下标对象、走完整的 `lst[i]` 查找流程。`for` 优先走迭代器协议也有效率上的考虑。

### 2.4 顺带对比:`in` 运算符的优先级不一样

**`in` 运算符**先找 `__contains__`,没有再找 `__iter__`,最后才退到 `__getitem__`。这也是给自定义类实现 `__contains__` 能加速成员判断的原因。

### 2.5 结论

现代 Python 里给自己的类实现遍历,一律实现 `__iter__`(通常是生成器),`__getitem__` 只用于需要下标访问的序列语义,不作为遍历手段。

---

## 三、总结

这两块知识背后是同一个思想:**Python 的 `for` 循环和遍历行为建立在"协议"之上,而不是类型检查**。

- 迭代器协议:`__iter__` 描述容器,`__next__` 描述游标,生成器一把梭;
- `for` 优先 `__iter__`,`__getitem__` 只是兜底的旧协议;`in` 优先 `__contains__`。

与 FastAPI 的联系:Pydantic 模型、`request.stream()`、文件上传的 `file`、数据库查询结果(如 SQLAlchemy 的 `Result`)都按迭代器协议工作;`async for` 是同一套思想的异步版,对应 `__aiter__`/`__anext__`,SSE 流式响应就是靠它逐块吐数据的。
