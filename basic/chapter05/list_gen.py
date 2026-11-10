# 列表推导式
my_list = [i + 1 for i in range(10)]
print(my_list)

# 复杂的操作
def handle_item(item):
    return item * item

my_list = [handle_item(item) for item in range(10)]
print(my_list)

# 列表生成式
# [0, 1, 1, 2, 3, 5, 8]
list_gen = (i for i in range(10))
print(type(list_gen))
mylist = list(list_gen)
print(type(mylist))
print(mylist)

# 字典推导式
my_dict = {"key" + str(i): i * i for i in range(10)}
print(type(my_dict))
print(my_dict)

# 集合推导式
my_set = {i for i in range(10)}
print(type(my_set))
print(my_set)