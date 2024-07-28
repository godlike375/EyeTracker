from collections import deque
from itertools import repeat


class MovingAverageDenoiser:
    def __init__(self, mean_count: int):
        self._count = mean_count
        self._buffer = None
        self._sum = 0

    def add(self, elem):
        if not self._buffer:
            self._buffer = deque(repeat(elem, self._count))
            self._sum = sum(self._buffer)
        self._sum += elem - self._buffer.popleft()
        self._buffer.append(elem)

    def max_min_diff(self, a, b):
        return abs(abs(max(a,b)) - abs(min(a, b)))

    def add_if_diff_from_avg(self, elem, diff_by: float = 0.33333):
        if not self._buffer:
            self._buffer = deque(repeat(elem, self._count))
            self._sum = sum(self._buffer)
        avg = self.get()
        if elem > avg and self.max_min_diff(max(self._buffer), avg) * diff_by < self.max_min_diff(avg, elem):
            self.add(elem)

        if elem < avg and self.max_min_diff(min(self._buffer), elem) * diff_by < self.max_min_diff(avg, elem):
            self.add(elem)

    def get(self):
        if not self._buffer:
            return 0
        return self._sum / self._count
