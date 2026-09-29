"""示例代码文件：供 read_file / search_code 工具演示使用。"""


def fib(n: int) -> int:
    """返回斐波那契数列第 n 项（0-indexed）。"""
    if n < 2:
        return n
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def is_prime(x: int) -> bool:
    if x < 2:
        return False
    for i in range(2, int(x ** 0.5) + 1):
        if x % i == 0:
            return False
    return True
