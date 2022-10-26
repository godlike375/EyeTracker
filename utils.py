from copy import copy
from dataclasses import dataclass
from threading import Thread
from time import sleep

# TODO: сделать загрузку из файла конфига

#https://gist.github.com/awesomebytes/0483e65e0884f05fb95e314c4f2b3db8
def threaded(fn):
    #To use as decorator to make a function call threaded.
    def wrapper(*args, **kwargs):
        thread = Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
        return thread
    return wrapper

@threaded
def thread_loop_caller(func, interval):
    while True:
        func()
        sleep(interval)

@dataclass
class XY:
    __slots__ = ['x', 'y']
    x: float
    y: float

    def __iter__(self):
        return iter((self.x, self.y))

    def __sub__(self, other):
        return XY(self.x - other.x, self.y - other.y)

    def __imul__(self, other):
        if type(other) is XY:
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
        if type(other) is XY:
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
        if type(other) is XY:
            self.x += other.x
            self.y += other.y
        elif type(other) is float or type(other) is int:
            self.x += other
            self.y += other
        else:
            raise ValueError('incorrect right operand')
        return self

    def __abs__(self):
        return XY(abs(self.x), abs(self.y))

    def __ge__(self, other):
        return self.x >= other.x or self.y >= other.y

    def to_int(self):
        return XY(int(self.x), int(self.y))
