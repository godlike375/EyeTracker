from dataclasses import dataclass
from functools import partial
from time import time, sleep

from common.abstractions import Cancellable, ProcessBased, Calibrator
from common.coordinates import Point
from common.logger import logger
from common.settings import AREA, OBJECT, CALIBRATE_LASER_COMMAND_ID, settings, MIN_THROTTLE_DIFFERENCE
from common.thread_helpers import threaded
from model.move_controller import MoveController
from model.selector import AreaSelector, ObjectSelector
from view import view_output
from view.view_model import SELECTION_MENU_NAME
from view.drawing import Processor

PERCENT_FROM_DECIMAL = 100


class OnScreenService:
    def __init__(self, model):
        self.on_screen_selectors = dict()  # {name: Selector}
        self._model = model

    def add_selector(self, selector, name):
        self.on_screen_selectors[name] = selector

    def remove_selector(self, name):
        if name in self.on_screen_selectors:
            del self.on_screen_selectors[name]
        self._model.state_control.change_tip(f'{name} selected', happened=False)
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


class SelectingService(Cancellable):
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

        return True

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
        return True

    def try_create_selector(self, name, retry_select_object_in_calibrating=False, additional_callback=None):

        if OBJECT in name:
            if not self.is_object_selection_allowed(retry_select_object_in_calibrating):
                return

        if AREA in name:
            if not self.is_area_selection_allowed(dont_reselect_area=retry_select_object_in_calibrating):
                return

        self._screen.remove_selector(name)

        return self.create_selector(name, additional_callback)


class LaserService():
    def __init__(self, state_control, debug_on=False):
        self._laser_controller = MoveController(debug_on=debug_on)
        self.initialized = self._laser_controller.initialized
        self.errored = False
        self.state_control = state_control

        MAX_LASER_RANGE = settings.MAX_LASER_RANGE_PLUS_MINUS
        left_top = Point(-MAX_LASER_RANGE, -MAX_LASER_RANGE)
        right_top = Point(MAX_LASER_RANGE, -MAX_LASER_RANGE)
        right_bottom = Point(MAX_LASER_RANGE, MAX_LASER_RANGE)
        left_bottom = Point(-MAX_LASER_RANGE, MAX_LASER_RANGE)
        self.laser_borders = [left_top, right_top, right_bottom, left_bottom]

    def calibrate_laser(self):
        logger.debug('laser calibrated')
        self._laser_controller._move_laser(Point(0, 0), command=CALIBRATE_LASER_COMMAND_ID)
        self.errored = False
        self._laser_controller._errored = False

    def center_laser(self):
        logger.debug('laser centered')
        self._laser_controller._move_laser(Point(0, 0))

    def move_laser(self, x, y):
        logger.debug(f'laser moved to {x, y}')
        self._laser_controller._move_laser(Point(x, y))

    def controller_is_ready(self):
        return self._laser_controller.can_send and self._laser_controller.is_ready

    def refresh_data(self):
        self._laser_controller.read_line()

    def set_new_position(self, position: Point):
        self.refresh_data()
        if self._laser_controller.is_errored:
            self.errored = True
            view_output.show_error('Контроллер лазера внезапно дошёл до предельных координат. \n'
                                   'Необходимо откалибровать контроллер лазера повторно. '
                                   'До этого момента слежение за объектом невозможно')
            self.state_control.change_tip('laser calibrated', False)
            return None
        if self.controller_is_ready():
            self._laser_controller.set_new_position(position)
            return True
        return False


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
            EventCheck('camera connected', False, 'Подключите камеру'),
            EventCheck('laser connected', False, 'Подключите контроллер лазера'),
            EventCheck('laser calibrated', False, 'Откалибруйте лазер'),
            EventCheck('noise threshold calibrated', False, 'Откалибруйте шумоподавление'),
            EventCheck('coordinate system calibrated', False,
                       'Откалибруйте координатную систему или выделите область вручную'),
            EventCheck('object selected', False, 'Выделите объект слежения')
        )

    def change_tip(self, event_name: str, happened=True):
        if event_name == 'coordinate system changed':
            for event in self._all_events:
                # TODO: Похоже на баг. Зачем сбрасывать первые 3 события, если изменилась координатная система?
                #  Наоборот по идее надо сбрасывать все остальные
                if event.name not in (e.name for e in self._all_events[:3]):
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


class NoiseThresholdCalibrator(ProcessBased, Cancellable, Calibrator):
    CALIBRATION_THRESHOLD_STEP = 0.0025

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
            settings.NOISE_THRESHOLD_PERCENT += NoiseThresholdCalibrator.CALIBRATION_THRESHOLD_STEP
            self._last_position = center
            self._last_timestamp = time()
            return False
        elif time() - self._last_timestamp > settings.THRESHOLD_CALIBRATION_DURATION:
            self.cancel()
            return True

    def _calibration_progress(self):
        return int(((time() - self._last_timestamp) / settings.THRESHOLD_CALIBRATION_DURATION) * PERCENT_FROM_DECIMAL)

    def _threshold_calibrating(self, center):
        if self._is_calibration_successful(center):
            return True

        progress_value = self._calibration_progress()
        if abs(self._progress - progress_value) > MIN_THROTTLE_DIFFERENCE:
            self._view_model.set_progress(progress_value)

    @threaded
    def calibrate(self):
        settings.NOISE_THRESHOLD_PERCENT = 0.0
        object = self._model.screen.get_selector(OBJECT)
        while True:
            if not self.in_progress:
                exit()
            sleep(self._delay_sec)
            if self._threshold_calibrating(object.center):
                break
        self._on_calibrated()

    def _on_calibrated(self):
        self._model.tracker.cancel()
        self._model.screen.remove_selector(OBJECT)
        self._model.try_restore_previous_area()
        settings.NOISE_THRESHOLD_PERCENT = round(settings.NOISE_THRESHOLD_PERCENT, 5)
        self._model.state_control.change_tip('noise threshold calibrated')
        self._model.state_control.change_tip('object selected', happened=False)
        view_output.show_message('Калибровка шумоподавления успешно завершена.')
        self._view_model.set_menu_state('all', 'normal')
        self.finish()

    def cancel(self):
        super().cancel()
        settings.NOISE_THRESHOLD_PERCENT = 0.0
        self._view_model.set_menu_state('all', 'normal')


class CoordinateSystemCalibrator(ProcessBased, Calibrator):
    def __init__(self, model, view_model):
        super().__init__()
        self._model = model
        self._view_model = view_model
        self._laser_borders = model.laser.laser_borders
        self._delay_sec = 1 / settings.FPS_VIEWED
        self._area = None

    @threaded
    def calibrate(self):
        object = self._model.screen.get_selector(OBJECT)
        area = self._model.selecting.create_selector(AREA)
        progress = 0
        self._wait_for_controller_ready()

        for point in self._laser_borders:
            self._model.laser.set_new_position(point)
            self._wait_for_controller_ready()

            area.left_button_click(object.center)
            progress += 25
            self._view_model.set_progress(progress)

        self._area = area
        self._on_calibrated()

    def _wait_for_controller_ready(self):
        while not self._model.laser.controller_is_ready():
            if not self.in_progress:
                exit()
            self._model.laser.refresh_data()
            sleep(self._delay_sec)

    def _on_calibrated(self):
        self._model.screen.remove_selector(OBJECT)

        self._view_model.set_progress(0)
        self._view_model.progress_bar_set_visibility(False)

        self._view_model.set_menu_state('all', 'normal')
        self._model.state_control.change_tip('object selected', happened=False)
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
        super().cancel()
        self._view_model.set_menu_state('all', 'normal')
