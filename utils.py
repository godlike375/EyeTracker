from dataclasses import dataclass

# TODO: сделать загрузку из файла конфига
@dataclass
class Settings:
    CAMERA_ID = 1 # the second web-camera
    FPS = 60 # frames per second
    SECOND = 1000 # ms
    CALL_EVERY = int(SECOND/FPS)

@dataclass
class XY:
    __slots__ = ['x', 'y']
    x: float
    y: float

    def __iter__(self):
        return iter((self.x, self.y))

class Pipeline:
    def __init__(self, *functions):
        self._funcs = list(functions)

    def run_pure(self, *data_args, **data_kwargs):
        first, *others = self._funcs
        result = first(*data_args, **data_kwargs)
        for func in others:
            result = func(result)
        return result

    def append_back(self, func):
        self._funcs.append(func)

    def append_front(self, func):
        self._funcs.insert(0, func)
