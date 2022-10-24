from collections import deque
from copy import copy
from itertools import repeat
from dataclasses import dataclass

# TODO: сделать загрузку из файла конфига
from tkinter import Tk

import cv2


@dataclass
class Settings:
    CAMERA_ID = 1  # the second web-camera
    FPS = 40  # frames per second
    SECOND = 1000  # ms
    CALL_EVERY = int(SECOND / FPS)
    BANDWIDTH = 115200
    TIMEOUT = 0.01
    PORT = 'com8'
    MEAN_TRACKING_COUNT = 3
    NOISE_THRESHOLD = 0.035
    MAX_HEIGHT = 800
    WINDOW_SIZE = '800x635'
    MAX_RANGE = 6000
    RESOLUTION = 12000


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


class FrameStorage:
    def __init__(self):
        self._raw_frame = None
        self._processed_image = None

    def get_image(self):
        if self._processed_image is None:
            raise RuntimeError('processed image was not initialized before being got')
        return self._processed_image

    def get_raw_frame(self):
        if self._raw_frame is None:
            raise RuntimeError('raw frame was not initialized before being got')
        return self._raw_frame


class Extractor:

    def __init__(self, source: int, root: Tk, frame_storage: FrameStorage):
        self.root = root
        self.frame_storage = frame_storage
        self.set_source(source)
        self.extract_frame()

    def set_source(self, source):
        self.camera = cv2.VideoCapture(source)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, Settings.MAX_HEIGHT)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, Settings.MAX_HEIGHT)
        if self.camera.isOpened():
            return
        print("Video camera is not found")
        exit()

    def extract_frame(self):
        _, frame = self.camera.read()
        self.frame_storage._raw_frame = frame  # the only one who can do it
        self.root.after(Settings.CALL_EVERY, self.extract_frame)
        return frame


class Denoiser:
    def __init__(self, init_value, mean_count):
        self.count = mean_count
        self.buffer = deque(repeat(init_value, mean_count))
        self.sum = sum(self.buffer)

    def add(self, elem):
        self.sum += elem - self.buffer.popleft()
        self.buffer.append(elem)

    def get(self):
        return self.sum / self.count