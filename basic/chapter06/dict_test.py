from collections.abc import Mapping
from copy import deepcopy

# 集合
mydict = {"a": {"name": "zhangsan"}, "b": 2, "c": 3}

# 浅copy
copy = mydict.copy()
print(mydict)
copy["a"]["name"] = "lisi"
print(mydict)
print(copy)
print("-" * 20)

# 深copy
copy = deepcopy(mydict)
print(mydict)
copy["a"]["name"] = "wangwu"
print(mydict)
print(copy)
print("-" * 20)

# get
print(mydict.get("d", {"age": 10}))
print("-" * 20)

# setDefault
mydict.setdefault("e", {"sex": "boy"})
print(mydict)
print("-" * 20)


#pop
value = mydict.pop("e")
print(value)
print(mydict)
print("-" * 20)

#popitem
value = mydict.popitem()
print(value)
print(mydict)
print("-" * 20)

#update
mydict.update({"key": "value"})
print(mydict)
mydict.update([("key1", "value1")])
print(mydict)
mydict.update((("key2", "value2"), ("key3", "value3")))
print(mydict) 


mydict.update({
    frozenset("abcdefg"): {"a": 1, "b": 2}
})
print(mydict)