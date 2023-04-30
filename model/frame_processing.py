from collections import deque
from itertools import chain, repeat
from time import time, sleep

import dlib

from common.abstractions import ProcessBased, RectBased, Drawable, Cancellable
from common.coordinates import Point, calc_center
from common.logger import logger
from common.settings import settings, OBJECT, AREA, MIN_THROTTLE_DIFFERENCE
from common.thread_helpers import threaded
from view import view_output
from view.drawing import Processor

PERCENT_FROM_DECIMAL = 100


class Tracker(RectBased, Drawable, ProcessBased, Cancellable):
    def __init__(self, mean_count=settings.MEAN_COORDINATES_FRAME_COUNT):
        ProcessBased.__init__(self)
        self._mean_count = mean_count
        self.tracker = dlib.correlation_tracker()
        self._denoisers: list[Denoiser] = []
        self._length_xy = None
        self._center = None
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
        center = calc_center(left_cur_pos, right_cur_pos)
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
        return self._center

    def draw_on_frame(self, frame):
        frame = Processor.draw_rectangle(frame, self.left_top, self.right_bottom)
        return Processor.draw_circle(frame, self._center)


class NoiseThresholdCalibrator(ProcessBased):
    CALIBRATION_THRESHOLD_STEP = 0.0025

    # В течение settings.THRESHOLD_CALIBRATION_DURATION секунд цель трекинга не должна двигаться
    def __init__(self, model, view_model):
        super().__init__()
        self._last_position = None
        self._last_timestamp = time()
        self._model = model
        self._view_model = view_model
        self._delay_sec = 1 / settings.FPS_PROCESSED

    def _is_calibration_successful(self, center):
        if self._last_position is None:
            self._last_position = center
            self._last_timestamp = time()
            return False
        if not (center == self._last_position):
            settings.NOISE_THRESHOLD_PERCENT += NoiseThresholdCalibrator.CALIBRATION_THRESHOLD_STEP
            self._last_position = center
            self._last_timestamp = time()
            return False
        elif time() - self._last_timestamp > settings.THRESHOLD_CALIBRATION_DURATION:
            self.stop()
            return True

    def _calibration_progress(self):
        return int(((time() - self._last_timestamp) / settings.THRESHOLD_CALIBRATION_DURATION) * PERCENT_FROM_DECIMAL)

    def _threshold_calibrating(self, center):
        if self._is_calibration_successful(center):
            self.stop()

        progress_value = self._calibration_progress()
        if abs(self._view_model.get_progress() - progress_value) > MIN_THROTTLE_DIFFERENCE:
            self._view_model.set_progress(progress_value)

    @threaded
    def calibrate(self):
        object = self._model.selecting.get_selector(OBJECT)
        while self.in_progress:
            sleep(self._delay_sec)
            self._threshold_calibrating(object._center)
        self._on_calibrated()

    def _on_calibrated(self):
        self._model.tracker.stop()
        self._model.selecting.stop_drawing(OBJECT)
        self._model.restore_previous_area()
        settings.NOISE_THRESHOLD_PERCENT = round(settings.NOISE_THRESHOLD_PERCENT, 5)
        self._model.state_tip.change_tip('noise threshold calibrated')
        self._model.state_tip.change_tip('object selected', happened=False)
        view_output.show_message('Калибровка шумоподавления успешно завершена.')


class CoordinateSystemCalibrator(ProcessBased):
    def __init__(self, model, view_model):
        super().__init__()
        self._model = model
        self._view_model = view_model
        self._laser_borders = model.laser.laser_borders
        self._delay_sec = 1 / settings.FPS_VIEWED

    @threaded
    def calibrate(self):
        object = self._model.selecting.get_selector(OBJECT)
        area = self._model.selecting.create_selector(AREA)
        progress = 0
        self._wait_for_controller_ready()

        for point in self._laser_borders[:-1]:
            self._model.laser.set_new_position(point)
            self._wait_for_controller_ready()

            screen_position = ((object.left_top + object.right_bottom) / 2).to_int()
            area.left_button_click(screen_position)

            progress += 25
            self._view_model.set_progress(progress)

        last_point = self._laser_borders[-1]
        self._model.laser.set_new_position(last_point)
        self._wait_for_controller_ready()
        screen_position = ((object.left_top + object.right_bottom) / 2).to_int()
        area._points.append(screen_position)

        self._finish_calibrating(area)

    def _wait_for_controller_ready(self):
        while not self._model.laser.controller_is_ready():
            if not self.in_progress:
                exit()
            self._model.laser.refresh_data()
            sleep(self._delay_sec)

    def _finish_calibrating(self, area):
        self._model.tracker.stop()
        self._model.selecting.stop_drawing(OBJECT)

        self._view_model.set_progress(0)
        self._view_model.progress_bar_set_visibility(False)

        area.finish_selecting()
        if area.is_empty:
            view_output.show_error('Необходимо повторить калибровку на более близком расстоянии '
                                   'камеры от области лазера.')
            self._model.state_tip.change_tip('object selected', happened=False)
            self.stop()
            return

        self._model.area_controller.set_area(area, self._laser_borders)
        view_output.show_message('Калибровка координатной системы успешно завершена.')
        self._model.state_tip.change_tip('area selected')
        self._model.state_tip.change_tip('coordinate system calibrated')
        self._model.state_tip.change_tip('object selected', happened=False)
        self.stop()
        self._model.center_laser()


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
