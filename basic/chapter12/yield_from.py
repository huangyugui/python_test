def sub():
    total = 0
    nums = []
    while True:
        num = yield
        if not num:
            break;
        print(f'销量为：{num}')
        total += num
        nums.append(num)
    return total, nums

def main(name):
    print(f'开始统计{name}:')
    # yield from 建立了__main__和 sub的通道，同时yield from 可以获取到sub方法中return的值
    # yield from其实就是catch了StopIteration，然后获取了e.value的值
    result = yield from sub()
    print(f'统计结果为：{result}')

if __name__ == '__main__':
    data = {
        "眼镜": [110, 120, 150],
        "电脑": [1100, 1900, 1800]
    }

    for key, value in data.items():
        gen = main(key)
        gen.send(None)
        for v in value:
            gen.send(v)
        try:
            gen.send(None)
        except StopIteration as e:
            pass