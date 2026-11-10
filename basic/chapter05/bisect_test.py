import bisect

# 使用bisect管理可排序的序列，底层使用的是二分法
mylist = []
bisect.insort(mylist, 9)
bisect.insort(mylist, 1)
bisect.insort(mylist, 4)
bisect.insort(mylist, 7)
bisect.insort(mylist, 3)
bisect.insort(mylist, 8)
print(mylist)