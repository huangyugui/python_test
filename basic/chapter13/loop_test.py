#事件循环+回调（驱动生成器（协程））+epoll(IO多路复用)

import asyncio

loop = asyncio.get_event_loop()
loop.run_until_complete()
asyncio.wait()
asyncio.get_running_loop()