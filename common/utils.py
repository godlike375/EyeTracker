from copy import copy
from dataclasses import dataclass
from threading import Thread, Event, current_thread
from time import sleep

LOGGER_NAME = 'default'


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


# https://stackoverflow.com/questions/323972/is-there-any-way-to-kill-a-thread
class StoppableThread(Thread):
    # Thread class with a stop() method

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event = Event()

    def stop(self):
        self._stop_event.set()

    def is_stopped(self):
        return self._stop_event.is_set()


# https://gist.github.com/awesomebytes/0483e65e0884f05fb95e314c4f2b3db8
def threaded(fn):
    # To use as decorator to make a function call threaded
    def wrapper(*args, **kwargs):
        thread = StoppableThread(target=fn, args=args, kwargs=kwargs)
        return thread

    return wrapper


@threaded
def thread_loop_runner(func, interval: float = 0.05):
    while True:
        sleep(interval)
        if current_thread().is_stopped():
            exit(0)
        func()


@dataclass
class Point:
    __slots__ = ['x', 'y']
    x: float
    y: float

    def __iter__(self):
        return iter((self.x, self.y))

    def __sub__(self, other):
        return Point(self.x - other.x, self.y - other.y)

    def __imul__(self, other):
        if type(other) is Point:
            self.x *= other.x
            self.y *= other.y
        elif type(other) is float or type(other) is int:
            self.x *= other
            self.y *= other
        else:
            raise ValueError('incorrect right operand')
        return self

    def __mul__(self, other):
        self = copy(self)
        if type(other) is Point:
            self.x *= other.x
            self.y *= other.y
        elif type(other) is float or type(other) is int:
            self.x *= other
            self.y *= other
        else:
            raise ValueError('incorrect right operand')
        return self

    def __add__(self, other):
        self = copy(self)
        if type(other) is Point:
            self.x += other.x
            self.y += other.y
        elif type(other) is float or type(other) is int:
            self.x += other
            self.y += other
        else:
            raise ValueError('incorrect right operand')
        return self

    def __abs__(self):
        return Point(abs(self.x), abs(self.y))

    def __ge__(self, other):
        return self.x >= other.x or self.y >= other.y

    def __lt__(self, other):
        return self.x < other.x or self.y < other.y

    def to_int(self):
        return Point(int(self.x), int(self.y))


class ThreadLoopable:
    def __init__(self, loop_func, interval: float, run_immediately: bool = True):
        if run_immediately:
            self.start_thread(loop_func, interval)

    def start_thread(self, loop_func, interval):
        self._thread_loop = thread_loop_runner(loop_func, interval)
        self._thread_loop.start()

    def stop_thread(self):
        self._thread_loop.stop()
