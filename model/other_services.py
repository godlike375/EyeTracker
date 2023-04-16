from collections import OrderedDict
from typing import List

from common.abstractions import Drawable
from common.coordinates import Point
from common.logger import logger
from common.settings import AREA, OBJECT, TRACKER, CALIBRATE, settings
from model.move_controller import MoveController
from model.selector import AreaSelector, ObjectSelector
from view import view_output
from common.thread_helpers import run_thread_after_func


class SelectingService:
    def __init__(self, area_selected_callback, object_selected_callback):
        self._active_drawn_objects = dict()  # {name: Selector}
        self.object_is_selecting = False
        self._on_area_selected = area_selected_callback
        self._on_object_selected = object_selected_callback

    def load_selected_area(self, area):
        area_selector = AreaSelector(AREA, self._on_area_selected, area)
        if area_selector.is_empty:
            return
        area_selector._selected = True
        self.start_drawing(area_selector, AREA)
        self._on_area_selected()

    def stop_drawing(self, name):
        if name in self._active_drawn_objects:
            del self._active_drawn_objects[name]

    def start_drawing(self, selector, name):
        self._active_drawn_objects[name] = selector

    def check_emptiness(self, selector, name):
        if selector is None or selector.is_empty:
            logger.warning('selected area is zero in size')
            view_output.show_message('Выделенная область слишком мала или некорректно выделена.', 'Ошибка')
            self.stop_drawing(name)

    def get_active_objects(self) -> List[Drawable]:
        return self._active_drawn_objects.values()

    def create_selector(self, name, additional_callback=None):
        logger.debug(f'creating new selector {name}')

        on_selected = self._on_object_selected if OBJECT in name else self._on_area_selected

        if additional_callback is not None:
            on_selected = run_thread_after_func(on_selected, additional_callback)

        selector = ObjectSelector(name, on_selected) if OBJECT in name else AreaSelector(name, on_selected)
        self._active_drawn_objects[name] = selector
        return selector

    def get_selector(self, name):
        return self._active_drawn_objects.get(name)

    def selector_exists(self, name):
        return name in self._active_drawn_objects

    def selector_is_selected(self, name):
        selector = self._active_drawn_objects.get(name)
        if selector is None:
            return False
        return selector.is_selected

    def cancel_selecting(self):
        if not self.selector_exists(AREA):
            return
        self.get_selector(AREA).cancel_selecting()
        self.stop_drawing(AREA)
        if not self.selector_exists(OBJECT):
            return
        object = self.get_selector(OBJECT)
        self.stop_drawing(OBJECT)
        self.object_is_selecting = False
        if object.name == TRACKER:
            return
        object.cancel_selecting()

    def check_selected(self, name):
        selector = self.get_selector(name)
        self.check_emptiness(selector, name)
        if not self.selector_is_selected(name):
            return False, None
        return True, selector


class LaserService():
    def __init__(self):
        self._laser_controller = MoveController(serial_off=False)
        self.initialized = self._laser_controller.initialized
        self.errored = False

        MAX_LASER_RANGE = settings.MAX_LASER_RANGE_PLUS_MINUS
        left_top = Point(-MAX_LASER_RANGE, -MAX_LASER_RANGE)
        right_top = Point(MAX_LASER_RANGE, -MAX_LASER_RANGE)
        right_bottom = Point(MAX_LASER_RANGE, MAX_LASER_RANGE)
        left_bottom = Point(-MAX_LASER_RANGE, MAX_LASER_RANGE)
        self.laser_borders = [left_top, right_top, right_bottom, left_bottom]

    def calibrate_laser(self):
        logger.debug('laser calibrated')
        self._laser_controller._move_laser(Point(0, 0), command=CALIBRATE)
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
            view_output.show_fatal('Контроллер лазера внезапно встал на концевик. Это непредвиденная ситуация. '
                                   'Необходимо откалибровать контроллер лазера повторно. '
                                   'До этого момента слежения за объектом невозможно')
            return None
        if self.controller_is_ready():
            self._laser_controller.set_new_position(position)
            return True
        return False


class StateTipSupervisor:
    EVENT_STATE_PRIORITY = OrderedDict(
        {
            'program started': 'Подключите все необходимые устройства (лазер и камеру)',
            'devices connected': 'Откалибруйте лазер',
            'laser calibrated': 'Настройте поворот и отражение изображения, затем откалибруйте шумоподавление',
            'noise threshold calibrated': 'Выделите область отслеживания',
            'area selected': 'Выделите объект отслеживания',
            'object selected': 'Активен сеанс отслеживания объекта'
        })

    def __init__(self, view_model):
        self._view_model = view_model
        self._state = 'program started'

    def next_state(self, event: str):
        event_keys = list(StateTipSupervisor.EVENT_STATE_PRIORITY.keys())
        state_index = event_keys.index(self._state)
        event_index = event_keys.index(event)
        if abs(state_index - event_index) == 1:
            self._state = event
        self._view_model.set_tip(self.current_state_to_tip())

    def current_state_to_tip(self):
        return StateTipSupervisor.EVENT_STATE_PRIORITY[self._state]
