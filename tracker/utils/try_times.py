import time
from typing import Callable


def try_few_times(action: Callable, times: int = 2, interval: float = 0.01):
    for _ in range(times):
        try:
            action()
            break
        except:
            time.sleep(interval)