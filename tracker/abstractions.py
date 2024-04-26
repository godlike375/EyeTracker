import pickle
import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class MutableVar:
    value: object = None

    def get(self) -> object:
        return self.value

    def set(self, another: object):
        self.value = another


class Packable:
    def pack(self) -> bytes:
        return pickle.dumps(self)

    @classmethod
    def unpack(cls, bytes) -> 'Packable':
        return pickle.loads(bytes)


class ID(int):...


def try_few_times(action: Callable, times: int = 2, interval: float = 0.01):
    for _ in range(times):
        try:
            action()
            return True
        except:
            if interval > 0:
                time.sleep(interval)
    return False


def try_one_time(action: Callable):
        try:
            action()
            return True
        except:
            return False