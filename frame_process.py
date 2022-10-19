from tkinter import Tk

import cv2
from PIL import Image
import dlib

from utils import Settings

class Processor:
    # white
    COLOR_WHITE = (255, 255, 255)
    COLOR_RED = (0, 0, 255)
    THICKNESS = 2
    CURRENT_COLOR = COLOR_WHITE

    @staticmethod
    def frame_to_image(frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb = Image.fromarray(rgb)
        return rgb
    @staticmethod
    def draw_rectangle(frame, left_top, right_bottom, color=None, thickness=None):
        color = color or Processor.COLOR_WHITE
        thickness = thickness or Processor.THICKNESS
        rect_frame = cv2.rectangle(frame, left_top, right_bottom, color, thickness)
        return Processor.frame_to_image(rect_frame)

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
        self.frame_storage._raw_frame = frame # the only one who can do it
        self.root.after(Settings.CALL_EVERY, self.extract_frame)
        return frame

class Tracker:
    def __init__(self):
        self.tracker = dlib.correlation_tracker()

    def start_tracking(self, frame, start_point, end_point):
        self.tracker.start_track(frame, dlib.rectangle(*start_point, *end_point))

    def get_tracked_position(self, frame):
        self.tracker.update(frame)
        return self.tracker.get_position()

    def draw_tracked_rect(self, frame):
        rect = self.get_tracked_position(frame)
        left_top = (int(rect.left()), int(rect.top()))
        right_bottom = (int(rect.right()), int(rect.bottom()))
        rect_frame = Processor.draw_rectangle(frame, left_top, right_bottom)
        return rect_frame