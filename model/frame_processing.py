from collections import deque
from itertools import chain, repeat

import dlib

from common.coordinates import Point, RectBased
from common.settings import Settings
from common.logger import logger
from model.area_controller import AreaController
from view.drawing import Drawable, Processor


class Tracker(RectBased, Drawable):
    def __init__(self, mean_count=Settings.MEAN_TRACKING_COUNT):
        self._mean_count = mean_count
        self.tracker = dlib.correlation_tracker()
        self._denoisers: list[Denoiser] = []
        self._length_xy = None
        self._center = None
        self.in_progress = False

    @property
    def left_top(self):
        return (self._center - self._length_xy / 2).to_int()

    @property
    def right_bottom(self):
        return (self._center + self._length_xy / 2).to_int()

    def update_center(self):
        left_cur_pos = Point(int(self._denoisers[0].get()), int(self._denoisers[1].get()))
        right_cur_pos = Point(int(self._denoisers[2].get()), int(self._denoisers[3].get()))
        center = AreaController.calc_center(left_cur_pos, right_cur_pos)
        if abs(self._center - center) >= self._length_xy * Settings.NOISE_THRESHOLD:
            self._center = center

    def start_tracking(self, frame, left_top, right_bottom):
        logger.debug('tracking started')
        for coord in chain(left_top, right_bottom):
            self._denoisers.append(Denoiser(coord, mean_count=self._mean_count))
        self._length_xy = Point(abs(left_top.x - right_bottom.x),
                                abs(left_top.y - right_bottom.y))
        self._center = AreaController.calc_center(left_top, right_bottom)
        self.tracker.start_track(frame, dlib.rectangle(*left_top, *right_bottom))
        self.in_progress = True

    def stop_tracking(self):
        self.in_progress = False

    def get_tracked_position(self, frame) -> Point:
        self.tracker.update(frame)
        rect = self.tracker.get_position()
        for i, coord in enumerate(map(int, (rect.left(),
                                            rect.top(),
                                            rect.right(),
                                            rect.bottom()
                                            ))):
            self._denoisers[i].add(coord)
        self.update_center()
        return self._center

    def draw_on_frame(self, frame):
        frame = Processor.draw_rectangle(frame, self.left_top, self.right_bottom)
        return Processor.draw_circle(frame, self._center)


class Denoiser:
    def __init__(self, init_value: float, mean_count: int):
        self._count = mean_count
        self._buffer = deque(repeat(init_value, mean_count))
        self._sum = sum(self._buffer)

    def add(self, elem):
        self._sum += elem - self._buffer.popleft()
        self._buffer.append(elem)

    def get(self):
        return self._sum / self._count
