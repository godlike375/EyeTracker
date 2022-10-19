from dataclasses import dataclass


# TODO: сделать загрузку из файла конфига
from tkinter import Tk

import cv2


@dataclass
class Settings:
    CAMERA_ID = 1  # the second web-camera
    FPS = 60  # frames per second
    SECOND = 1000  # ms
    CALL_EVERY = int(SECOND / FPS)


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
        self.x *= other.x
        self.y *= other.y
        return self


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
    LAST_RESORT_CAMERA_SOURCE = 1

    def __init__(self, source: int, root: Tk, frame_storage: FrameStorage):
        self.root = root
        self.frame_storage = frame_storage
        self.set_source(source)
        self.extract_frame()

    def set_source(self, source):
        self.camera = cv2.VideoCapture(source)
        if self.camera.isOpened():
            return
        self.camera = cv2.VideoCapture(Extractor.LAST_RESORT_CAMERA_SOURCE)
        if not self.camera.isOpened():
            print("Video camera is not found")
            exit()

    def extract_frame(self):
        _, frame = self.camera.read()
        self.frame_storage._raw_frame = frame  # the only one who can do it
        self.root.after(Settings.CALL_EVERY, self.extract_frame)
        return frame