from dataclasses import dataclass
from functools import partial
from time import time, sleep

import numpy as np

from eye_tracker.common.abstractions import ProcessBased, Calibrator
from eye_tracker.common.logger import logger
from eye_tracker.common.settings import AREA, OBJECT, settings, MIN_THROTTLE_DIFFERENCE
from eye_tracker.common.thread_helpers import threaded
from eye_tracker.model.selector import AreaSelector, ObjectSelector
from eye_tracker.view import view_output
from eye_tracker.view.drawing import Processor
from eye_tracker.view.view_model import SELECTION_MENU_NAME

PERCENT_FROM_DECIMAL = 100


class OnScreenService:
    def __init__(self, model):
        self.on_screen_selectors = dict()  # {name: Selector}
        self._model = model

    def add_selector(self, selector, name):
        self.on_screen_selectors[name] = selector

    def remove_selector(self, name):
        if name not in self.on_screen_selectors:
            return
        del self.on_screen_selectors[name]
        self._model.state_control.change_state(f'{name} selected', happened=False)
        if OBJECT in name:
            self._model.tracker.cancel()

    def get_selector(self, name):
        return self.on_screen_selectors.get(name)

    def selector_exists(self, name):
        return name in self.on_screen_selectors

    def prepare_image(self, frame):
        frame = Processor.resize_to_minimum(frame)
        processed = self._draw_active_objects(frame)
        return Processor.frame_to_image(processed)

    def _draw_active_objects(self, frame):
        for obj in self.on_screen_selectors.values():
            frame = obj.draw_on_frame(frame)
        return frame


class SelectingService(ProcessBased):
    def __init__(self, area_selected_callback, object_selected_callback, model, screen, view_model):
        self._on_area_selected = area_selected_callback
        self._on_object_selected = object_selected_callback
        self._model = model
        self._screen = screen
        self._view_model = view_model

    def load_selected_area(self, area):
        area_selector = AreaSelector(AREA, self._on_area_selected, area)
        if area_selector.is_empty:
            return
        area_selector._is_done = True
        area_selector._in_progress = False
        self._screen.add_selector(area_selector, AREA)
        self._on_area_selected()

    def check_emptiness(self, selector, name):
        if selector is None or selector.is_empty:
            logger.warning('selected area is too small in size')
            view_output.show_error('Выделенная область слишком мала или некорректно выделена.', 'Ошибка')
            self._screen.remove_selector(name)

    def create_selector(self, name, call_func_after_selection=None):
        logger.debug(f'creating new selector {name}')

        on_selected = self._on_object_selected if OBJECT in name else self._on_area_selected

        if call_func_after_selection is not None:
            on_selected = partial(on_selected, call_func_after_selection)

        selector = ObjectSelector(name, on_selected) if OBJECT in name else AreaSelector(name, on_selected)
        self._screen.add_selector(selector, name)
        self._view_model.set_menu_state('all', 'disabled')
        return selector

    def selecting_is_done(self, name):
        return self._screen.selector_exists(name) and self._screen.get_selector(name).is_done

    def selecting_in_progress(self, name):
        return self._screen.selector_exists(name) and self._screen.get_selector(name).in_progress

    def cancel(self):
        self._model.state_control.change_state('enter pressed')
        for name in (AREA, OBJECT):
            if not self._screen.selector_exists(name):
                continue
            if not self.selecting_is_done(name):
                self._screen.get_selector(name).cancel()
                self._screen.remove_selector(name)

    def check_selected_correctly(self, name):
        selector = self._screen.get_selector(name)
        self.check_emptiness(selector, name)
        if not self.selecting_is_done(name):
            return False, None
        return True, selector

    def is_object_selection_allowed(self, select_in_calibrating):
        if select_in_calibrating:
            return True

        if self.selecting_is_done(OBJECT):
            confirm = view_output.ask_confirmation('Выделенный объект перестанет отслеживаться. Продолжить?')
            if not confirm:
                return False

        return self.selecting_is_done(AREA)

    def is_area_selection_allowed(self, dont_reselect_area):
        # TODO: поправить логику и сделать без костылей вроде этого
        if dont_reselect_area:
            return False

        tracking_stop_question = ''
        if self.selecting_is_done(OBJECT):
            tracking_stop_question = 'Слежение за целью будет остановлено. '
        if self.selecting_is_done(AREA):
            confirm = view_output.ask_confirmation(f'{tracking_stop_question}'
                                                   f'Выделенная область будет стёрта. Продолжить?')
            if not confirm:
                return False
        self._screen.remove_selector(OBJECT)
        self._model.state_control.change_state('coordinate system calibrated', happened=False)
        return True

    def try_create_selector(self, name, reselect_while_calibrating=False, additional_callback=None):

        if OBJECT in name:
            if not self.is_object_selection_allowed(reselect_while_calibrating):
                return

        if AREA in name:
            if not self.is_area_selection_allowed(dont_reselect_area=reselect_while_calibrating):
                return

        self._screen.remove_selector(name)

        if OBJECT in name:
            self._model.state_control.change_state('enter pressed', happened=False)

        return self.create_selector(name, additional_callback)


@dataclass
class EventCheck:
    __slots__ = ['name', 'happened', 'tip']
    name: str
    happened: bool
    tip: str


class StateMachine:
    def __init__(self, view_model):
        self._view_model = view_model
        # Расположены в порядке приоритета от наибольшего к наименьшему
        self._all_events = (
            EventCheck('enter pressed', True, 'Выделите объект, отрегулируйте стрелками положение и нажмите Enter'
                                              '\n для подтверждения выделения'),
            EventCheck('calibrating finished', True, 'Происходит процесс калибровки'),
            EventCheck('camera connected', False, 'Подключите камеру'),
            EventCheck('laser connected', False, 'Подключите контроллер лазера'),
            EventCheck('laser calibrated', False, 'Откалибруйте лазер'),
            EventCheck('noise threshold calibrated', False, 'Откалибруйте шумоподавление'),
            EventCheck('coordinate system calibrated', False,
                       'Откалибруйте координатную систему или выделите область вручную'),
            EventCheck('object selected', False, 'Выделите объект слежения')
        )

    def change_state(self, event_name: str, happened=True):
        if event_name == 'coordinate system changed':
            for event in self._all_events[:2]:
                event.happened = True
            for event in self._all_events[6:]:
                event.happened = False

        for event in self._all_events:
            if event_name == event.name:
                event.happened = happened

        prioritized = self._most_prioritized_event()
        if prioritized is None:
            self._view_model.set_tip('')
            return
        self._view_model.set_tip(prioritized.tip)

        if prioritized.name == 'object selected':
            self._view_model.set_menu_state(SELECTION_MENU_NAME, 'normal')
        else:
            self._view_model.set_menu_state(SELECTION_MENU_NAME, 'disabled')

    def _most_prioritized_event(self):
        for event in self._all_events:
            if not event.happened:
                return event


class NoiseThresholdCalibrator(ProcessBased, Calibrator):
    CALIBRATION_THRESHOLD_STEP = 0.25

    # В течение settings.THRESHOLD_CALIBRATION_DURATION секунд цель трекинга не должна двигаться
    def __init__(self, model, view_model):
        super().__init__()
        self._last_position = None
        self._last_timestamp = time()
        self._model = model
        self._view_model = view_model
        self._delay_sec = 1 / settings.FPS_PROCESSED
        self._progress = 0

    def _is_calibration_successful(self, center):
        if self._last_position is None:
            self._last_position = center
            self._last_timestamp = time()
            return False
        if not (center == self._last_position):
            settings.NOISE_THRESHOLD_RANGE += NoiseThresholdCalibrator.CALIBRATION_THRESHOLD_STEP
            self._last_position = center
            self._last_timestamp = time()
            return False
        elif time() - self._last_timestamp > settings.THRESHOLD_CALIBRATION_DURATION:
            self.finish()
            return True

    def _calibration_progress(self):
        return int(((time() - self._last_timestamp) / settings.THRESHOLD_CALIBRATION_DURATION) * PERCENT_FROM_DECIMAL)

    def _calibrating_finish(self, center):
        if self._is_calibration_successful(center):
            return True

        progress_value = self._calibration_progress()
        if abs(self._progress - progress_value) > MIN_THROTTLE_DIFFERENCE:
            self._view_model.set_progress(progress_value)

    @threaded
    def calibrate(self):
        self._model.state_control.change_state('calibrating finished', happened=False)
        settings.NOISE_THRESHOLD_RANGE = 0.0
        object = self._model.screen.get_selector(OBJECT)
        while True:
            if not self.in_progress:
                exit()
            sleep(self._delay_sec)
            if self._calibrating_finish(object.center):
                break
        self._on_calibrated()

    def _on_calibrated(self):
        self._model.tracker.cancel()
        self._model.screen.remove_selector(OBJECT)
        self._model.try_restore_previous_area()
        self._model.state_control.change_state('noise threshold calibrated')
        settings.NOISE_THRESHOLD_RANGE = round(settings.NOISE_THRESHOLD_RANGE, 3)
        view_output.show_message('Калибровка шумоподавления успешно завершена.')

    def cancel(self):
        if not self.in_progress:
            return
        super().cancel()
        settings.NOISE_THRESHOLD_RANGE = 0.0
        self._view_model.set_menu_state('all', 'normal')

    def finish(self):
        super().finish()
        self._model.state_control.change_state('calibrating finished')
        self._view_model.set_menu_state('all', 'normal')


class CoordinateSystemCalibrator(ProcessBased, Calibrator):
    def __init__(self, model, view_model):
        super().__init__()
        self._model = model
        self._view_model = view_model
        self._laser_borders = model.laser.laser_borders
        self._delay_sec = 1 / settings.FPS_VIEWED
        self._area = None

    def get_object_center(self, object):
        return object.center

    def limit_coordinate(self, coordinate, min, max):
        return min if coordinate < min else max if coordinate > max else coordinate

    def normalize_coordinates(self, object, frame_shape):
        ltx, lty = object.left_top
        rbx, rby = object.right_bottom
        ltx = self.limit_coordinate(ltx, 0, frame_shape[1])
        rbx = self.limit_coordinate(rbx, 0, frame_shape[1])
        lty = self.limit_coordinate(lty, 0, frame_shape[0])
        rby = self.limit_coordinate(rby, 0, frame_shape[0])
        return ltx, rbx, lty, rby

    @threaded
    def calibrate(self):
        self._model.state_control.change_state('calibrating finished', happened=False)
        object: ObjectSelector = self._model.screen.get_selector(OBJECT)
        area = self._model.selecting.create_selector(AREA)
        progress = 0
        self._wait_for_controller_ready()
        sleep(0.075)
        # без засыпания в object попадают невалидные (видимо старые) данные
        ltx, rbx, lty, rby = self.normalize_coordinates(object, self._model._current_frame.shape)
        cropped_frame = self._model._current_frame[lty:rby, ltx:rbx]
        blured = Processor.blur_image(cropped_frame)
        masks = Processor.cluster_pixels(blured, num_clusters=4)
        mask1 = Processor.get_biggest_mask(masks)
        masks = [m for m in masks if id(m) != id(mask1)]
        mask2 = Processor.get_biggest_mask(masks)
        masks = [m for m in masks if id(m) != id(mask2)]
        mask3 = Processor.get_biggest_mask(masks)
        mask1_ranges = Processor.get_color_ranges(mask1)
        mask2_ranges = Processor.get_color_ranges(mask2)
        mask3_ranges = Processor.get_color_ranges(mask3)
        united_ranges = (np.array([one if one < two else two for one, two in zip(mask1_ranges[0], mask2_ranges[0])]),
                         np.array([one if one > two else two for one, two in zip(mask1_ranges[1], mask2_ranges[1])]))
        united_ranges = (np.array([one if one < two else two for one, two in zip(united_ranges[0], mask3_ranges[0])]),
                         np.array([one if one > two else two for one, two in zip(united_ranges[1], mask3_ranges[1])]))
        self._model.filtered_ranges = united_ranges

        for point in self._laser_borders:
            self._model.laser.set_new_position(point)
            logger.debug(f'setting laser position {point.x, point.y}')
            self._wait_for_controller_ready()
            area_point = self.get_object_center(object)
            area.left_button_click(area_point)
            progress += 25
            self._view_model.set_progress(progress)

        self._area = area
        self._on_calibrated()

    def _wait_for_controller_ready(self):
        while not self._model.laser.controller_is_ready():
            if not self.in_progress:
                exit()
            sleep(self._delay_sec)

    def _on_calibrated(self):
        self._model.screen.remove_selector(OBJECT)

        self._view_model.set_progress(0)
        self._view_model.progress_bar_set_visibility(False)
        self._model.state_control.change_state('object selected', happened=False)
        if self._area.is_empty:
            view_output.show_error('Необходимо повторить калибровку на более близком расстоянии '
                                   'камеры от области лазера.')
            self.cancel()
            return

        self._model.area_controller.set_area(self._area, self._laser_borders)
        view_output.show_message('Калибровка координатной системы успешно завершена.')
        self.finish()
        self._model.center_laser()

    def cancel(self):
        if not self.in_progress:
            return
        super().cancel()
        self._view_model.set_menu_state('all', 'normal')

    def finish(self):
        super().finish()
        self._model.state_control.change_state('calibrating finished')
        self._view_model.set_menu_state('all', 'normal')
