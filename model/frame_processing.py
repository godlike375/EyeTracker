from collections import deque
from itertools import chain, repeat
from time import time, sleep

import dlib

from common.coordinates import Point
from common.abstractions import ProcessBased, RectBased, Drawable
from common.logger import logger
from common.settings import settings, TRACKER, OBJECT, AREA
from model.area_controller import AreaController
from view.drawing import Processor
from common.thread_helpers import threaded


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
        self.is_selected = True # Для перевыделения объекта

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

    def start_tracking(self, frame, left_top, right_bottom):
        logger.debug('tracking started')
        frame = Processor.resize_frame_relative(frame, settings.DOWNSCALE_FACTOR)
        self._length_xy = Point(abs(left_top.x - right_bottom.x),
                                abs(left_top.y - right_bottom.y))

        left_top, right_bottom = \
            (left_top * settings.DOWNSCALE_FACTOR).to_int(), \
            (right_bottom * settings.DOWNSCALE_FACTOR).to_int()
        for coord in chain(left_top, right_bottom):
            self._denoisers.append(Denoiser(coord, mean_count=self._mean_count))
        self._center = AreaController.calc_center(left_top, right_bottom)
        self.tracker.start_track(frame, dlib.rectangle(*left_top, *right_bottom))
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
    def __init__(self, laser_service, selecting_service, area_controller):
        super().__init__()
        self._get_selector = selecting_service.get_selector
        self._stop_drawing = selecting_service.stop_drawing
        self._set_area = area_controller.set_area

        MAX_LASER_RANGE = settings.MAX_LASER_RANGE_PLUS_MINUS
        self._max_laser_range = MAX_LASER_RANGE

        left_top = Point(-MAX_LASER_RANGE, -MAX_LASER_RANGE)
        right_top = Point(MAX_LASER_RANGE, -MAX_LASER_RANGE)
        right_bottom = Point(MAX_LASER_RANGE, MAX_LASER_RANGE)
        left_bottom = Point(-MAX_LASER_RANGE, MAX_LASER_RANGE)

        points = [left_top, right_top, right_bottom, left_bottom]
        self._laser_points = [point for point in points]

        self._controller_is_ready = laser_service.controller_is_ready
        self._refresh_data = laser_service.refresh_data
        self._move_to_point = laser_service.set_new_position

    @threaded
    def calibrate(self):
        object = self._get_selector(OBJECT)
        screen_points = []

        for point in self._laser_points:
            while not self._controller_is_ready():

                if not self.in_progress:
                    exit()
                self._refresh_data()
                sleep(0.25)

            self._move_to_point(point)
            while not self._controller_is_ready():

                if not self.in_progress:
                    exit()
                self._refresh_data()
                sleep(0.25)
            screen_position = ((object.left_top + object.right_bottom) / 2).to_int()
            screen_points.append(screen_position)

            print(screen_position)
        area = self._get_selector(AREA)
        area._points = screen_points
        area._selected = True
        self._set_area(area, self._laser_points)
        self._stop_drawing(OBJECT)
        # TODO: сравнить координаты, по которым посылали лазер и реальные координаты
        self.stop()
        # TODO: чтобы не мешаться в главном потоке логикой вызова move laser и ожидания, можно создать отдельный поток

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
