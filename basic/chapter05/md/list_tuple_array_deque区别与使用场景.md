# Python 序列容器对比：list / tuple / array / deque

> 存放位置：`basic\chapter05\md\list_tuple_array_deque区别与使用场景.md`
> 前置知识：可变与不可变对象、序列索引、运算符重载（chapter05 增强赋值文档）、numpy 概念
> 配套验证：本文所有数据均在 `D:\python\fastapi_test\.venv`（Python 3.13）实测得出

## 一句话结论

- **list**：通用可变序列，日常首选。
- **tuple**：不可变序列，固定结构/可哈希场景。
- **array**：同质数值的紧凑数组，省内存 + 二进制 I/O。
- **deque**：双端队列，两端 O(1) 增删。

**选型口诀**：默认用 list；要"只读/打包/当字典键"用 tuple；要"省内存存同质数值"用 array；要"队列/栈/两端操作"用 deque。

## 1. 四者定位一句话表

| 容器 | 本质 | 一句话定位 | 来自 |
|---|---|---|---|
| `list` | 动态数组 | 通用可变序列，随机访问快、扩容自动 | 内置 |
| `tuple` | 固定数组 | 不可变记录/打包，可哈希 | 内置 |
| `array` | C 风格数组 | 同质数值紧凑存储 + 文件互转 | 内置 `array` 模块 |
| `deque` | 双端队列 | 两端 O(1) 增删的队列/栈 | `collections.deque` |

## 2. 多维对比表

| 维度 | list | tuple | array | deque |
|---|---|---|---|---|
| 可变 | ✅ | ❌ | ✅ | ✅ |
| 元素类型 | 任意混合 | 任意混合 | **同质数值**（type code） | 任意混合 |
| 随机访问 `a[i]` | O(1) | O(1) | O(1) | O(1)（两端更快） |
| 尾部增删 | O(1) | — | O(1) 均摊 | O(1) |
| **头部增删** | **O(n)**（移动全部元素） | — | O(n) | **O(1)** |
| 中间插入/删除 | O(n) | — | O(n) | O(n) |
| 内存占用 | 较大（对象指针+预分配） | 较小（固定） | **最小**（原生 C 类型） | 最大（块状链表） |
| 可哈希（字典键/set） | ❌ | ✅ | ❌ | ❌ |
| 向量化数学运算 | ❌（逐元素循环） | ❌ | ❌ | ❌ |
| 二进制文件互转 | ❌ | ❌ | ✅ `tofile/fromfile` | ❌ |
| 线程安全单操作 | 否（多线程需锁） | — | 否 | **是**（append/pop 原子） |

## 3. 实测数据（Python 3.13，本机）

### 3.1 内存对比：同样 1000 个整数

```
getsizeof:
  list      : 8056 字节
  tuple     : 8040 字节
  array('i'): 4200 字节   ← 最省（约 list 的一半）
  deque     : 8680 字节   ← 最费
```

### 3.2 头部操作性能：pop(0)+insert(0) ×1000 次

```
list  pop(0)+insert(0): 0.3459 s   ← 每次都要搬移全部元素
deque popleft+appendleft: 0.0012 s  ← 约快 288 倍
```

### 3.3 类型限制与哈希

```python
array('i', [1, 2.5])   # TypeError: 'float' object cannot be interpreted as an integer
hash((1, 2))           # ok          ← 只有 tuple 可哈希
hash([1, 2])           # TypeError: unhashable type: 'list'
hash(array('i',[1,2])) # TypeError: unhashable type: 'array.array'
hash(deque([1,2]))     # TypeError: unhashable type: 'collections.deque'
```

## 4. 使用场景

| 场景 | 推荐 | 为什么 |
|---|---|---|
| 通用可变序列、顺序遍历、随机访问 | **list** | 全能默认项，API 返回/参数首选 |
| 固定结构数据（坐标、记录、配置对） | **tuple** | 语义上"打包不可变"，防误改 |
| 字典键 / set 元素 | **tuple** | 唯一可哈希的序列容器 |
| 函数返回多个值 | **tuple** | `return x, y` 本质就是打包 |
| 大量同质数值、内存敏感 | **array** | 原生类型连续存储，省内存 |
| 与 C/二进制/文件交互 | **array** | `tofile/fromfile/tobytes` 直接读写 |
| FIFO 队列 / 生产者-消费者 | **deque** | 两端 O(1)，`popleft` 不为难 |
| 栈（LIFO） | **list 或 deque** | list 尾部 O(1)；deque 亦可 |
| 滑动窗口 / 固定长度缓存 | **deque(maxlen=n)** | 满员自动弹出旧元素 |
| 多线程下简单队列 | **deque** | append/pop 是原子操作（仍需锁做复合操作） |
| 数值矩阵运算、科学计算 | **numpy.ndarray**（array 的加强版） | 向量化 + 全套运算符 |

### 场景示例代码

```python
from array import array
from collections import deque

# tuple：打包与解包（异构固定结构）
point = (3, 5)
x, y = point
d = {point: "原点附近"}          # 可哈希 → 能做字典键

# array：紧凑数值存储 + 二进制文件
arr = array('i', [10, 20, 30])   # 只能放 int
arr.append(40)
with open("nums.bin", "wb") as f:
    arr.tofile(f)                # 直接写二进制，无需循环

# deque：双端操作 + 定长
dq = deque([1, 2, 3], maxlen=5)  # 上限 5 个
dq.appendleft(0)                 # 左端 O(1)
dq.append(4); dq.append(5)       # 右端 O(1)，超过 maxlen 自动丢旧
print(dq)                        # deque([0, 1, 2, 3, 4], maxlen=5)

# deque 做 FIFO 队列
q = deque(["task1", "task2"])
while q:
    print(q.popleft())           # task1 / task2，头部弹出 O(1)

# list：通用场景
tasks = [t for t in range(5)]    # 推导式、排序、切片都是 list 强项
print(sorted(tasks, reverse=True)[:3])
```

## 5. 坑与注意

1. **list 的 `pop(0)` / `insert(0, x)` 是 O(n)**：处理头部操作会整体搬移元素。要频繁两端操作就用 deque；`pop(0)` 换成 `dq.popleft()` 性能差 200 倍以上。
2. **tuple 的"不可变"是引用层面**：`(1, [2])` 里 list 仍可变——tuple 不可变的是元素指向，不是元素内容。
3. **array 没有向量化**：`arr + arr` 在 array 上语义是"拼接"（类似 list），不是逐元素相加！要做逐元素运算得用循环或转 numpy。
4. **deque 中间访问慢**：`dq[5000]` 是 O(n)（要从最近一端走），deque 定位中间元素比 list 慢；随机访问密集场景用 list。
5. **array 类型码要选对**：`'i'`（int）/`'f'`（float）/`'d'`（double）等；放错类型直接 TypeError（见 3.3）。

## 6. 一句话记忆

> list 是"万能数组"，tuple 是"不可变打包"，array 是"省内存的同质数值仓"，deque 是"两头都能进出的队列"。性能关键：**头尾频繁进出找 deque，随机访问找 list，纯数值省内存找 array，只读/键值找 tuple**。

## 7. 呼应章节

- numpy（文档 6.3 提及）：array 的"加强版"——array 只解决存储紧凑，numpy 还给了向量化运算和全套运算符重载（含 `@=`），数值密集场景应从 array 升级到 numpy。
- chapter05 `Python增强赋值运算符全家桶.md`：list/deque/array 的 `+=` 行为、共享引用陷阱在本文件 5.1 均有体现。
- OOP 第 4 章 4.4/4.5：tuple 不可变 vs list 可变的差异，正是"对象内部状态"可变性概念的实际应用。
