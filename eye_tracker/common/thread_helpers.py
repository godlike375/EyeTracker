from sys import exit
from threading import (
    Thread, Event, current_thread
)
from time import sleep, time
from dataclasses import dataclass


# https://stackoverflow.com/questions/323972/is-there-any-way-to-kill-a-thread
class StoppableThread(Thread):
    # Thread class with a stop() method

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event = Event()

    def stop(self):
        self._stop_event.set()

    @property
    def is_stopped(self):
        return self._stop_event.is_set()


# https://gist.github.com/awesomebytes/0483e65e0884f05fb95e314c4f2b3db8
def threaded(fn):
    # To use as decorator to make a function call threaded
    def wrapper(*args, **kwargs):
        thread = StoppableThread(target=fn, args=args, kwargs=kwargs)
        return thread

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
    while True:
        if current_thread().is_stopped:
            exit()
        func_time = time()
        func()
        func_time = time() - func_time
        time_to_sleep = interval.value - func_time
        if time_to_sleep > 0:
            sleep(time_to_sleep)



class ThreadLoopable:
    def __init__(self, loop_func, interval: MutableValue, run_immediately: bool = True):
        self._loop_func = loop_func
        self._interval = interval
        if run_immediately:
            self.start_thread(loop_func, interval)

    def start_thread(self, loop_func, interval):
        self._thread_loop = thread_loop_runner(loop_func, interval)
        self._thread_loop.start()

    def stop_thread(self):
        self._thread_loop.stop()

    def __enter__(self):
        self.start_thread(self._loop_func, self._interval)
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.stop_thread()
        if exc_value:
            raise exc_value
