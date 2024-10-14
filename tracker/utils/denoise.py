from collections import deque
from itertools import repeat


def max_min_diff(a, b):
    return abs(abs(max(a, b)) - abs(min(a, b)))


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

    def add_if_diff_from_avg(self, elem, diff_by: float = 0.33333):
        if not self._buffer:
            self._buffer = deque(repeat(elem, self._count))
            self._sum = sum(self._buffer)
        avg = self.get()
        if elem > avg and max_min_diff(max(self._buffer), avg) * diff_by < max_min_diff(avg, elem):
            self.add(elem)

        if elem < avg and max_min_diff(min(self._buffer), elem) * diff_by < max_min_diff(avg, elem):
            self.add(elem)

    def get(self):
        if not self._buffer:
            return 0
        return self._sum / self._count

class MovingAverageDenoiser2D:
    def __init__(self, mean_count: int):
        self.x_denoiser = MovingAverageDenoiser(mean_count)
        self.y_denoiser = MovingAverageDenoiser(mean_count)

    def add(self, elem):
        self.x_denoiser.add(elem[0])
        self.y_denoiser.add(elem[1])

    def add_if_diff_from_avg(self, elem, diff_by: float = 0.33333):
        self.x_denoiser.add_if_diff_from_avg(elem[0], diff_by)
        self.y_denoiser.add_if_diff_from_avg(elem[1], diff_by)

    def get(self):
        return self.x_denoiser.get(), self.y_denoiser.get()

class MovingAverageDenoiser3D:
    def __init__(self, mean_count: int):
        self.x_denoiser = MovingAverageDenoiser(mean_count)
        self.y_denoiser = MovingAverageDenoiser(mean_count)
        self.z_denoiser = MovingAverageDenoiser(mean_count)

    def add(self, elem):
        self.x_denoiser.add(elem[0])
        self.y_denoiser.add(elem[1])
        self.z_denoiser.add(elem[2])

    def add_if_diff_from_avg(self, elem, diff_by: float = 0.33333):
        self.x_denoiser.add_if_diff_from_avg(elem[0], diff_by)
        self.y_denoiser.add_if_diff_from_avg(elem[1], diff_by)
        self.z_denoiser.add_if_diff_from_avg(elem[2], diff_by)

    def get(self):
        return self.x_denoiser.get(), self.y_denoiser.get(), self.z_denoiser.get()
