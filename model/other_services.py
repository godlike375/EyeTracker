from dataclasses import dataclass
from functools import partial

from common.abstractions import Cancellable
from common.coordinates import Point
from common.logger import logger
from common.settings import AREA, OBJECT, CALIBRATE_LASER_COMMAND_ID, settings
from model.move_controller import MoveController
from model.selector import AreaSelector, ObjectSelector
from view import view_output
from view.view_model import SELECTION_MENU_NAME
from view.drawing import Processor


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
    def __init__(self, area_selected_callback, object_selected_callback, model, screen):
        self._on_area_selected = area_selected_callback
        self._on_object_selected = object_selected_callback
        self._model = model
        self._screen = screen

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
            view_output.show_error('Контроллер лазера внезапно дошёл до предельных координат. Ситуация внештатная. \n'
                                   'Необходимо откалибровать контроллер лазера повторно. '
                                   'До этого момента слежения за объектом невозможно')
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
