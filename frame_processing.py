from itertools import chain

import cv2
import dlib
from PIL import Image

from utils import Denoiser, XY, Settings
from area_controller import AreaController


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
        rect_frame = cv2.rectangle(frame, (*left_top,), (*right_bottom,), Processor.CURRENT_COLOR, Processor.THICKNESS)
        return rect_frame


class Tracker:
    # TODO: возможно стоит добавить разностный трекинг (разница между 2-3 кадрами, определить так движение)
    def __init__(self, mean_count=Settings.MEAN_TRACKING_COUNT):
        self.mean_count = mean_count
        self.tracker = dlib.correlation_tracker()
        self.denoisers: list[Denoiser] = []
        self.length_xy = None
        self._center = None

    @property
    def left_top(self):
        return (self._center - self.length_xy * 0.5).to_int()

    @property
    def right_bottom(self):
        return (self._center + self.length_xy * 0.5).to_int()

    @property
    def center(self):
        return self._center

    def update_center(self):
        left_cur_pos = XY(int(self.denoisers[0].get()), int(self.denoisers[1].get()))
        right_cur_pos = XY(int(self.denoisers[2].get()), int(self.denoisers[3].get()))
        center = AreaController.calc_center(left_cur_pos, right_cur_pos)
        if abs(self._center - center) >= self.length_xy * Settings.NOISE_THRESHOLD:
            self._center = center



    def start_tracking(self, frame, left_top, right_bottom):
        for coord in chain(left_top, right_bottom):
            self.denoisers.append(Denoiser(coord, mean_count=self.mean_count))
        self.length_xy = XY(abs(left_top.x - right_bottom.x), abs(left_top.y - right_bottom.y))
        self._center = AreaController.calc_center(left_top, right_bottom)
        self.tracker.start_track(frame, dlib.rectangle(*left_top, *right_bottom))


    def get_tracked_position(self, frame):
        self.tracker.update(frame)
        rect = self.tracker.get_position()
        for i, coord in enumerate(map(int, (rect.left(), rect.top(), rect.right(), rect.bottom()))):
            self.denoisers[i].add(coord)
        self.update_center()

    def draw_tracked_rect(self, frame):
        # для фильтрации надо left_top и right_bottom навеное сделать генераторами
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
