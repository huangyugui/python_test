myset = set()
myset.add("key")
print(myset)
print("-" * 20)


myset1 = {1, 2, 3, 5}
myset2 = {4, 5, 6}
diff = myset1.difference(myset2)
print(diff)
myset3 = myset1 - myset2
print(myset3)
myset4 = myset2 & myset1
print(myset4)
myset5 = myset1 | myset2
print(myset5)
myset6 = myset1 ^ myset2
print(myset6)

if 5 in myset1:
    print("5 is in myset6")

print(myset1.issubset(myset5))
