# dict /set 的实现原理（Python）与 HashMap / HashSet 对照（Java）

> 存放位置：
>
> `basic\chapter06\md\dict与set实现原理及Java对照.md`
> 前置知识：哈希函数、时间复杂度 O (1)/O (n)、链表与树
> 配套验证：
>
> **Python 侧全部在本机&#x20;**
>
> `.venv`
>
> **（Python 3.13）实测**
>
> ；
>
> **Java 侧基于 JDK 8（1.8.0_411）源码与规范描述，本机仅安装 JRE 无 javac，未能编译实测**
>
> ——Java 相关结论以 JDK 8 官方实现为准

## 一句话结论

**dict 和 set 的底层都是哈希表（hash table）**：dict = "哈希表 + 键值对"，set = "只有键的哈希表"。Python 3.7+ 的 dict 用紧凑双层结构（indices + entries）实现**保序 + 省内存**；Java 的 HashMap（8+）用 "数组 + 链表 + 红黑树" 实现**冲突树化**，HashSet 内部就是包了一层 HashMap。



***

## 1. 哈希表五要素（两种语言通用）



| 要素    | Python                                  | Java                                      |
| ----- | --------------------------------------- | ----------------------------------------- |
| 哈希函数  | 内建 `hash()`（str 用带进程随机盐的 SipHash，防碰撞攻击） | 用户覆写 `hashCode()` + 高位扰动 `h ^ (h >>> 16)` |
| 槽位计算  | `hash & (size-1)`                       | `(hash ^ (hash>>>16)) & (size-1)`         |
| 冲突解决  | **开放寻址**（线性 / 伪随机探测）                    | **链地址法**（桶内链表 → 红黑树）                      |
| 装载因子  | 2/3（约 0.667），超了扩容翻倍                     | 0.75，超了扩容翻倍                               |
| 可哈希要求 | 实现 `__hash__`；list/dict/set 不可哈希        | 覆写 `hashCode()`；可变对象做 key 同样危险            |

## 2. Python 侧实测（Python 3.13）

### 2.1 查找性能：哈希表 O (1) vs 列表 O (n)



```
list 查找 5000（×10000 次）: 0.2902 s
dict 查找 5000（×10000 次）: 0.0003 s   ← 约快 1000 倍
set  查找 5000（×10000 次）: 0.0013 s
```

### 2.2 哈希冲突退化的实证



```
class BadHash:
    def __hash__(self): return 1        # 所有对象哈希相同 → 全部冲突
    def __eq__(self, other): return self is other

bd = {BadHash(): i for i in range(200)}
# 全冲突时查找: 0.0051s（退化为接近线性探测 O(n)）
# 正常时查找:   0.0000s
```

结论：**冲突率决定哈希表性能**，自定义 `__hash__` 质量差会把平均 O (1) 拖成 O (n)。

### 2.3 不可哈希对象



```
list 做 key → TypeError: unhashable type: 'list'
set  做 key → TypeError: unhashable type: 'set'
```

可变对象哈希会随内容变化 → 已插入的 key 可能再也查不到，所以语言直接禁止。

### 2.4 插入顺序保持（3.7+ 语言保证）



```
d2 键顺序: [0, 1, 3, 4, 'a', 'b', 'c']   ← 删除后新插入的仍排尾部
```

### 2.5 扩容轨迹（装载因子 2/3，翻倍扩容）



```
(元素数, dict 字节):
(6, 352)   (8, 352)   (14, 632)   (30, 1168)   (62, 2264)
(126, 4688) (254, 9304) (510, 18512) (1000, 36952)
```

6→14→30→62→126→254→510→1000 附近容量跳变，正是 "元素数 > 容量 × 2/3 时翻倍 rehash" 的轨迹。

## 3. Python dict 的实现细节（CPython 3.13）

### 3.1 紧凑哈希表（compact dict）—— 两层结构

Python 3.6+ 的 dict 不再是 "一张稀疏大表"，而是 **indices + entries 两层**：



```
dict 对象 (PyDictObject)
├── ma_used           实际元素数
├── ma_version_tag    版本戳（迭代期间被修改 → 抛 RuntimeError 的依据）
└── ma_keys / ma_values
    ├── dk_size       槽位数（2 的幂：8、16、32…）
    ├── dk_usable     = dk_size × 2/3（可插入上限，装载因子 2/3 的来源）
    ├── dk_indices    稀疏索引表（长度 = dk_size，按需 1/2/4/8 字节/项，存 entries 下标或 -1）
    └── dk_entries    紧凑顺序表（按插入顺序 append，(hash, key, value) 三列连续存储）
```



```
dk_indices（按哈希槽索引，值 = entries 下标）
   [2] [0] [.] [1] [3] [.] [.] [.]
    0   1   2   3   4   5   6   7      ← dk_size = 8 的槽位（mask = 7）

dk_entries（按插入顺序）
   idx0: (hash_a, "a", 1)
   idx1: (hash_b, "b", 2)
   idx2: (hash_c, "c", 3)
```

关键点：**查找先走 indices（O (1) 拿到 entries 下标），再进 entries 比较 hash 和 key**；entries 本身只是 "按插入顺序排队的仓库"。

三个收益：



1. **保序**：entries 是 append-only，遍历顺序 = 插入顺序（实测 2.4）。

2. **省内存**：旧版（<3.6）在稀疏表的每个槽位都存 (hash, key, value) 三件套，且一半以上槽位常年为空；compact 版把三件套紧凑连续存进 entries，索引表按需 1/2/4/8 字节 —— 整体内存省约三分之一（实测空 dict 仅 64 字节）。

3. **删除高效**：删除只需把 entries 槽位标记 dummy、indices 对应位置 -1，不搬动其他元素（详见 3.3）。

### 3.2 开放寻址（open addressing）与探测公式

dict 没有 "链表桶"，冲突的 key 直接**占用表内其他空槽**。槽位定位：



```
首槽：i = hash & mask            （mask = dk_size - 1；2 的幂下等价取模且更快）

冲突后探测（CPython 公式）：
    perturb = hash
    i = (i * 5 + 1 + perturb) & mask
    perturb >>= 5                （PERTURB_SHIFT = 5）
    重复直到找到空槽或命中同 key
```

这个公式的两个设计要点：



1. **前几次近似线性探测**（`i*5+1`）：CPU 缓存友好，短距离冲突时开销极小。

2. **perturb 逐跳右移 5 位**：每跳都把哈希高位的新信息搅进来 —— 两个 "首槽相同" 的 key 很快就走不同的探测路径，**避免线性探测的 "主聚集"（primary clustering，长拥堵带）问题**。

### 逐步实例（本机模拟，mask=7，dk\_size=8）

先给出可复现的模拟器（完整复刻 CPython 探测公式）：



```
MASK = 7   # dk_size = 8

def probe_sequence(h, n=8):
    """复刻 CPython 探测公式，返回完整访问槽位序列"""
    perturb = h
    i = h & MASK
    seq = [i]
    for _ in range(n - 1):
        perturb >>= 5
        i = (i * 5 + 1 + perturb) & MASK
        seq.append(i)
    return seq
```

**例 1：三个 key 首槽全撞在槽 1（小哈希 → 纯线性）**

int 的 `hash(x) = x`，所以 `1&7 = 9&7 = 17&7 = 1`：



```
hash= 1  探测序列: [1, 6, 7, 4, 5, 2, 3, 0]
hash= 9  探测序列: [1, 6, 7, 4, 5, 2, 3, 0]
hash=17  探测序列: [1, 6, 7, 4, 5, 2, 3, 0]
```

三个序列**完全相同**：因为 `9>>5=0`、`17>>5=0`，`perturb` 一步归零，公式退化成 `i = (i*5+1) & 7` 的**纯线性探测**—— 小哈希都挤在同一段路上，这正是 "主聚集" 的成因，也是 `perturb` 要解决的问题。

**例 2：大哈希 → perturb 搅动路径分叉**



```
hash=1        序列: [1, 6, 7, 4, 5, 2, 3, 0]
hash=1048577  序列: [1, 6, 7, 4, 6, 7, 4, 5]   ← 路径分叉了！
```

`1048577 >> 5 = 32768` 非零，每跳都往 `i*5+1` 里掺入哈希高位的新信息 —— 两个 "首槽相同" 的 key 很快各走各路，避免拥堵带。

**例 3：完整插入过程（复刻 compact dict 状态）**



```
插入 key=       1: 首槽1 → 落槽1 (entry#0)
插入 key=       9: 首槽1 → 冲突→槽6 → 落槽6 (entry#1)
插入 key=      17: 首槽1 → 冲突→槽6 → 冲突→槽7 → 落槽7 (entry#2)
插入 key= 1048577: 首槽1 → 冲突→槽6 → 冲突→槽7 → 冲突→槽4 → 落槽4 (entry#3)
                                                          ← 前三个走线性，到这里 perturb 拐弯

最终 indices : [-1, 0, -1, -1, 3, -1, 1, 2]
                槽0  槽1  槽2  槽3  槽4  槽5  槽6  槽7     ← 槽1→entry0, 槽6→entry1, 槽7→entry2, 槽4→entry3
最终 entries : [(1, 1), (9, 9), (17, 17), (1048577, 1048577)]   ← 按插入顺序排队（保序的来源）
```

最后一步最精彩：前三个 key 沿线性路径 `1→6→7`，大哈希 `1048577` 在槽 7 被占后，**同一个公式靠 perturb 搅动把路径拐向槽 4**。

要点归纳：



* 因为 `dk_size` 是 2 的幂、`5` 与 `dk_size` 互质，探测序列在**用完所有槽位之前不会重复**（例 1 的 hash=1 序列覆盖了全部 8 个槽位）。

* 配合 2/3 装载因子，表满之前总能找到空位（实际永远不会满）。

### 3.3 插入 / 查找 / 删除的完整流程

**插入&#x20;**`d[key] = v`



```
① hash(key) → i = hash & mask
② dk_indices[i] == -1（空槽）→ 新 entry 追加到 entries 尾，
   dk_indices[i] = 新下标           ← 新元素永远进队尾（保序的来源）
③ 占用 → 按 3.2 公式探测下一槽，直到空槽或命中（先比 hash、再比 ==）
④ 若 used + 1 > dk_usable → 先扩容：dk_size 翻倍，
   全部条目重新计算位置（rehash），再执行 ②③
```

**查找&#x20;**`d[key]`



```
① hash(key) → i = hash & mask
② dk_indices[i] == -1 → KeyError
③ 非空 → entries[dk_indices[i]]：hash 不等 → 探测下一槽；
   hash 相等再比 == → 命中返回值；不等 → 探测下一槽
```

**删除&#x20;**`del d[key]`



```
① 按查找流程命中 entry
② entries 中该条目标记 dummy（key 换成哨兵对象，hash 保留）
③ dk_indices 对应槽置 -1
④ 尾部 dummy 可被下次插入复用；dummy 若在 entries 尾部则直接截断
```

为什么删除**不立刻搬动元素**？因为每个 entry 的位置被其他 key 的探测链 "引用"（indices 指向它），贸然搬动会打断别人的探测路径导致查找失效 —— 所以只留 "墓碑"（dummy 标记）。

### 3.4 两个进阶优化（CPython）



1. **split table（PEP 412 共享键）**：大量 "同构 dict"（如对象的 `__dict__`）共享同一套 keys（dk\_indices + dk\_entries 的 key 部分），每个 dict 只额外存自己的 value 数组 —— 实例化大量同类对象时内存大幅下降。

2. **str 哈希进程级随机盐（SipHash-1-3）**：每次启动进程随机生成盐，`hash("foo")` 不同进程不同 —— 防哈希碰撞 DoS（攻击者构造同哈希字符串把 dict 退化成 O (n)）。

## 4. Python set 的实现

set 与 dict 同源（CPython 里 set 与 dict 共用 `setentry`/ 哈希逻辑），差异：



* set 是**只有键、没有值**的哈希表（槽位存 (hash, key)）。

* 没有 dict 的 compact 双层优化（仍是单一稀疏表），所以**set 通常比同等规模的 dict 更省内存**（少存 value），但没有 "保序" 一说（set 本来无序）。

## 5. Java HashMap（JDK 8+）的实现

### 5.1 结构：数组 + 链表 + 红黑树（本机 JDK 1.8.0\_411 依据源码描述）



```
table（桶数组，默认长度 16，2 的幂）

  0  1   2   3   4 ...
  |  |   |   |   |
  A→B→C        D→E       ← 链表（哈希冲突挂同桶）
        ↘
  F→G→…→I     ← 单桶超过 8 个 → 树化为红黑树（查找 O(log n)）
```

关键参数（JDK 8 源码常量，本机 JRE 无法编译反射验证，以官方源码为准）：



| 参数                         | 值    | 含义                     |
| -------------------------- | ---- | ---------------------- |
| `DEFAULT_INITIAL_CAPACITY` | 16   | 初始桶数                   |
| `DEFAULT_LOAD_FACTOR`      | 0.75 | 元素数 > 容量 ×0.75 时扩容翻倍   |
| `TREEIFY_THRESHOLD`        | 8    | 单桶链表 ≥8 且容量 ≥64 → 转红黑树 |
| `UNTREEIFY_THRESHOLD`      | 6    | 树节点 ≤6 → 退化回链表         |
| `MIN_TREEIFY_CAPACITY`     | 64   | 树化的容量下限                |

### 5.2 关键行为



* **扰动函数**：`(h = key.hashCode()) ^ (h >>> 16)` —— 让高位也参与低位索引计算，降低碰撞。

* **索引**：`hash & (n-1)`（n 为 2 的幂，等价取模且更快）。

* **允许一个 null key**：null 哈希为 0，特判放入桶 0。

* **迭代无序**：扩容 rehash 后顺序就变，与 Python 保序相反。

* **非线程安全**：并发写需要 `ConcurrentHashMap`（JDK 8 用 CAS + 桶锁 + 红黑树）。

## 6. Java HashSet：本质是 "包了一层 HashMap"

HashSet 源码的核心（JDK 8）：



```
public class HashSet<E> extends AbstractSet<E> {
    private transient HashMap<E,Object> map;       // 内部持有 HashMap
    private static final Object PRESENT = new Object(); // 占位 value

    public boolean add(E e) {
        return map.put(e, PRESENT) == null;        // 元素当 key，value 恒为 PRESENT
    }
    public boolean contains(Object o) { return map.containsKey(o); }
    public boolean remove(Object o)  { return map.remove(o) == PRESENT; }
}
```

**结论：HashSet = "只有 key 的 HashMap"**，与 Python 的 "set = 只有键的 dict" 是同一设计思想。

## 7. 全面对比表



| 维度      | Python dict / set                  | Java HashMap / HashSet            |
| ------- | ---------------------------------- | --------------------------------- |
| 底层结构    | 哈希表（开放寻址）                          | 哈希表（链地址法）                         |
| 冲突解决    | 开放寻址：perturb 探测（见 3.2，近似线性 + 高位搅动） | 链地址法：链表 → 红黑树（≥8 树化）              |
| 最坏查找复杂度 | O (n)（全部冲突时退化为探测整张表）               | **O(log n)**（红黑树化后，Java 8+ 的上限更稳） |
| 顺序      | dict 保插入顺序（3.7+ 语言保证）              | 无序；`LinkedHashMap` 才有顺序           |
| 内存布局    | compact 双层（indices+entries），省内存    | 每个节点一个 Node 对象，开销更大               |
| 装载因子    | 2/3（dict 与 set）                    | 0.75                              |
| 扩容      | 翻倍 rehash，保留 2 的幂                  | 翻倍 rehash，保留 2 的幂                 |
| null 键  | None 就是普通对象，直接可用                   | 允许**一个** null key（特判桶 0）          |
| 哈希来源    | 内建 `hash()`，str 带随机盐防攻击            | 用户 `hashCode()` + 高位扰动            |
| 线程安全    | GIL 保护单操作原子性（复合操作仍需锁）              | 完全非线程安全（并发用 ConcurrentHashMap）    |
| 集合封装    | set 独立实现（单一表）                      | HashSet = HashMap 包装（PRESENT 占位）  |

## 8. 坑与建议



1. **可变对象做 key**：Python 直接拒绝（TypeError）；Java 不拒绝但语义危险 ——`hashCode` 随内容变，对象已入 HashMap 后改字段，`get` 将找不到。

2. `__eq__`**&#x20;必须搭配&#x20;**`__hash__`**&#x20;覆写**：Python 覆写 `__eq__` 后默认 `__hash__` 置 None（对象变不可哈希）；Java 同理（`hashCode` 与 `equals` 必须一致）。

3. **大数据量去重**：Python 用 `set` 去重 O (n)，list 逐项判断是 O (n²)；Java 同理由 HashSet 承担。

4. **扩容抖动**：两语言扩容都触发全量 rehash—— 预估规模时给初始容量（Java `new HashMap<>(n)`，Python 无参接口，通常无需关心）。

5. **迭代顺序依赖**：Java 代码绝不能依赖 HashMap 遍历顺序；Python dict 依赖顺序是安全的，但**set 仍是无序**（需要有序集合用 `sorted()` 或 `dict` 模拟）。

## 9. 一句话记忆

> **Python dict/set：开放寻址哈希表，compact 双层保序省内存；Java HashMap/HashSet：链地址哈希表，冲突树化保最坏 O (log n)；HashSet 就是 HashMap 的语法糖（PRESENT 占位）**
>
> 。两种语言把同一个 "哈希表" 做了不同的工程取舍：Python 要保序省内存，Java 要抗冲突上限。

## 10. 呼应章节



* chapter05 `list_tuple_array_deque区别与使用场景.md`：list 查找 O (n) vs dict/set 查找 O (1) 的实测即本文件 2.1。

* chapter05 `Python生成器详解.md`：`itertools.groupby` 等惰性工具与 dict 组合做流式分组。

* OOP 第 4 章 4.8 自省：`hash(obj)` / `isinstance(obj, collections.abc.Hashable)` 是判断 "能否做 key" 的标准自省手段。