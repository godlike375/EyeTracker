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


def try_few_times(action: Callable, times: int = 2, interval: float = 0.000001):
    for _ in range(times):
        try:
            action()
            break
        except:
            if times > 1:
                time.sleep(interval)