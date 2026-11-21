from dataclasses import dataclass
from threading import Thread, Event, current_thread
from time import sleep, time


class StoppableThread(Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event = Event()

    def stop(self):
        self._stop_event.set()

    @property
    def is_stopped(self):
        return self._stop_event.is_set()


def threaded(fn):
    def wrapper(*args, **kwargs):
        return StoppableThread(target=fn, args=args, kwargs=kwargs)

    return wrapper


@dataclass
class MutableValue:
    __slots__ = ['value']
    value: object


@threaded
def thread_loop_runner(func, interval: MutableValue = None):
    if interval is None:
        interval = MutableValue(0.05)
    sleep(interval.value)
    while not current_thread().is_stopped:
        func_time = time()
        func()
        time_to_sleep = interval.value - (time() - func_time)
        if time_to_sleep > 0:
            sleep(time_to_sleep)


class ThreadLoopable:
    def __init__(self, loop_func, interval: MutableValue, run_immediately: bool = True):
        self._loop_func = loop_func
        self._interval = interval
        self._thread_loop = None
        if run_immediately:
            self.start_thread()

    def start_thread(self):
        self._thread_loop = thread_loop_runner(self._loop_func, self._interval)
        self._thread_loop.start()

    def stop_thread(self):
        if self._thread_loop is not None:
            self._thread_loop.stop()
            self._thread_loop.join(timeout=2)
            self._thread_loop = None

    @property
    def is_running(self):
        return self._thread_loop is not None and self._thread_loop.is_alive()

    def __enter__(self):
        self.start_thread()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.stop_thread()
        if exc_value:
            raise exc_value
