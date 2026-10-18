from collections import deque
from itertools import repeat


class Denoiser:
    def __init__(self, init_value: float, mean_count: int):
        self._count = max(int(mean_count), 1)
        self._buffer = deque(repeat(init_value, self._count))
        self._sum = sum(self._buffer)

    def add(self, elem):
        self._sum += elem - self._buffer.popleft()
        self._buffer.append(elem)

    def get(self):
        return self._sum / self._count
