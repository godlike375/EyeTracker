import pickle
import time
from typing import Callable


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
            break
        except:
            time.sleep(interval)