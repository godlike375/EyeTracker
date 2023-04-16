from collections import deque
from itertools import chain, repeat
from time import time, sleep

import dlib

from common.abstractions import ProcessBased, RectBased, Drawable
from common.coordinates import Point
from common.logger import logger
from common.settings import settings, TRACKER, OBJECT, AREA
from common.thread_helpers import threaded
from model.area_controller import AreaController
from view.drawing import Processor

PERCENT_FROM_DECIMAL = 100


class Tracker(RectBased, Drawable, ProcessBased):
    def __init__(self, mean_count=settings.TRACKING_FRAMES_MEAN_NUMBER):
        self._mean_count = mean_count
        self.tracker = dlib.correlation_tracker()
        self._denoisers: list[Denoiser] = []
        self._length_xy = None
        self._center = None
        self.in_progress = False
        self.name = TRACKER
        self.is_selected = True  # Для перевыделения объекта

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
        if abs(self._center - center) >= self._length_xy * settings.NOISE_THRESHOLD_PERCENT:
            self._center = center

    def start_tracking(self, frame, scaled_left_top, scaled_right_bottom):
        logger.debug('tracking started')
        frame = Processor.resize_frame_relative(frame, settings.DOWNSCALE_FACTOR)
        self._length_xy = Point(abs(scaled_left_top.x - scaled_right_bottom.x),
                                abs(scaled_left_top.y - scaled_right_bottom.y))

        for coord in chain(scaled_left_top, scaled_right_bottom):
            self._denoisers.append(Denoiser(coord, mean_count=self._mean_count))

        scaled_left_top, scaled_right_bottom = \
            (scaled_left_top * settings.DOWNSCALE_FACTOR).to_int(), \
            (scaled_right_bottom * settings.DOWNSCALE_FACTOR).to_int()

        self._center = AreaController.calc_center(scaled_left_top, scaled_right_bottom)
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
        return self._center

    def draw_on_frame(self, frame):
        frame = Processor.draw_rectangle(frame, self.left_top, self.right_bottom)
        return Processor.draw_circle(frame, self._center)


class NoiseThresholdCalibrator(ProcessBased):
    CALIBRATION_THRESHOLD_STEP = 0.0025

    # В течение settings.OBJECT_NOT_MOVING_DURATION секунд цель трекинга не должна двигаться
    def __init__(self):
        super().__init__()
        self._last_position = None
        self._last_timestamp = time()

    def is_calibration_successful(self, center):
        if self._last_position is None:
            self._last_position = center
            self._last_timestamp = time()
            return False
        if not (center == self._last_position):
            settings.NOISE_THRESHOLD_PERCENT += NoiseThresholdCalibrator.CALIBRATION_THRESHOLD_STEP
            self._last_position = center
            self._last_timestamp = time()
            return False
        elif time() - self._last_timestamp > settings.OBJECT_NOT_MOVING_DURATION:
            self.in_progress = False
            return True

    def calibration_progress(self):
        return int(((time() - self._last_timestamp) / settings.OBJECT_NOT_MOVING_DURATION) * PERCENT_FROM_DECIMAL)


class CoordinateSystemCalibrator(ProcessBased):
    def __init__(self, model):
        super().__init__()
        self._model = model

        self._laser_borders = model.laser_service.laser_borders

    @threaded
    def calibrate(self):
        object = self._model.selecting_service.get_selector(OBJECT)
        screen_points = []

        self._wait_for_controller_ready()

        for point in self._laser_borders:
            self._model.laser_service.set_new_position(point)

            self._wait_for_controller_ready()

            screen_position = ((object.left_top + object.right_bottom) / 2).to_int()
            screen_points.append(screen_position)
        self._finish_calibrating(screen_points)

    def _wait_for_controller_ready(self):
        while not self._model.laser_service.controller_is_ready():
            if not self.in_progress:
                exit()
            self._model.laser_service.refresh_data()
            sleep(0.25)

    def _finish_calibrating(self, screen_points):
        area = self._model.selecting_service.get_selector(AREA)
        area._points = screen_points
        area.finish_selecting()
        self._model.area_controller.set_area(area, self._laser_borders)

        self._model.selecting_service.stop_drawing(OBJECT)
        self._model.tracker.stop()
        self.stop()


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
