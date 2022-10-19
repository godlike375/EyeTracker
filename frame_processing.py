import cv2
import dlib
from PIL import Image


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
    def draw_rectangle(frame, left_top, right_bottom):
        rect_frame = cv2.rectangle(frame, left_top, right_bottom, Processor.CURRENT_COLOR, Processor.THICKNESS)
        return rect_frame


class Tracker:
    def __init__(self):
        self.tracker = dlib.correlation_tracker()
        self.left_top = None
        self.right_bottom = None

    def start_tracking(self, frame, start_point, end_point):
        self.tracker.start_track(frame, dlib.rectangle(*start_point, *end_point))

    def get_tracked_position(self, frame):
        self.tracker.update(frame)
        rect = self.tracker.get_position()
        self.left_top = (int(rect.left()), int(rect.top()))
        self.right_bottom = (int(rect.right()), int(rect.bottom()))

    def draw_tracked_rect(self, frame):
        rect_frame = Processor.draw_rectangle(frame, self.left_top, self.right_bottom)
        return rect_frame


class FramePipeline:
    def __init__(self, *functions):
        self._funcs = list(functions)

    def run_pure(self, data_arg):
        if self._funcs:
            first, *others = self._funcs
            result = first(data_arg)
            for func in others:
                result = func(result)
            return result
        return data_arg

    def append_back(self, func):
        self._funcs.append(func)

    def append_front(self, func):
        self._funcs.insert(0, func)

    def pop_front(self):
        self._funcs.pop(0)
