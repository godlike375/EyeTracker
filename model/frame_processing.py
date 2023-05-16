from collections import deque
from itertools import chain, repeat

import dlib

from model.common.abstractions import ProcessBased, RectBased, Drawable, Cancellable
from model.common.coordinates import Point, calc_center
from model.common.logger import logger
from model.common.settings import settings
from view.drawing import Processor


class Tracker(RectBased, Drawable, ProcessBased, Cancellable):
    def __init__(self, mean_count=settings.MEAN_COORDINATES_FRAME_COUNT):
        ProcessBased.__init__(self)
        self._mean_count = mean_count
        self.tracker = dlib.correlation_tracker()
        self._denoisers: list[Denoiser] = []
        self._object_length_xy = None
        self._center = None

    @property
    def left_top(self):
        return self._center - self._object_length_xy // 2

    @property
    def right_bottom(self):
        return self._center + self._object_length_xy // 2

    @property
    def center(self):
        return self._center

    def update_center(self):
        left_cur_pos = Point(int(self._denoisers[0].get()), int(self._denoisers[1].get()))
        right_cur_pos = Point(int(self._denoisers[2].get()), int(self._denoisers[3].get()))
        center = calc_center(left_cur_pos, right_cur_pos)
        if abs(self.center - center) >= self._object_length_xy * settings.NOISE_THRESHOLD_PERCENT:
            self._center = center

    def start_tracking(self, frame, left_top, right_bottom):
        logger.debug('tracking started')
        frame = Processor.resize_frame_relative(frame, settings.DOWNSCALE_FACTOR)
        self._object_length_xy = Point(abs(left_top.x - right_bottom.x),
                                       abs(left_top.y - right_bottom.y))

        scaled_left_top, scaled_right_bottom = \
            (left_top * settings.DOWNSCALE_FACTOR).to_int(), \
            (right_bottom * settings.DOWNSCALE_FACTOR).to_int()

        for coord in chain(left_top, right_bottom):
            self._denoisers.append(Denoiser(coord, mean_count=self._mean_count))

        self._center = calc_center(scaled_left_top, scaled_right_bottom)
        self.tracker.start_track(frame, dlib.rectangle(*scaled_left_top, *scaled_right_bottom))
        self.start()

    def get_tracked_position(self, frame) -> Point:
        frame = Processor.resize_frame_relative(frame, settings.DOWNSCALE_FACTOR)
        self.tracker.update(frame)
        rect = self.tracker.get_position()
        for i, coord in enumerate(map(int, (rect.left() / settings.DOWNSCALE_FACTOR,
                                            rect.top() / settings.DOWNSCALE_FACTOR,
                                            rect.right() / settings.DOWNSCALE_FACTOR,
                                            rect.bottom() / settings.DOWNSCALE_FACTOR
                                            ))):
            self._denoisers[i].add(coord)
        self.update_center()
        return self.center

    def draw_on_frame(self, frame):
        frame = Processor.draw_rectangle(frame, self.left_top, self.right_bottom)
        return Processor.draw_circle(frame, self.center)


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
