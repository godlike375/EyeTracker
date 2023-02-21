from functools import partial
from tkinter import Tk, messagebox

from common.coordinates import Point
from common.logger import logger
from common.settings import OBJECT, AREA, Settings
from model.selector import LEFT_CLICK, LEFT_DOWN, LEFT_UP

MOUSE_EVENTS = ('<Button-1>', '<B1-Motion>', '<ButtonRelease-1>')


class ViewModel:
    def __init__(self, root: Tk):
        self._root = root
        self._model = None
        self._view = None

    def set_model(self, model):
        self._model = model

    def set_view(self, view):
        self._view = view

    def on_image_ready(self, image):
        self._view.set_current_image(image)

    def calibrate_laser(self):
        self._model.laser_service.calibrate_laser()

    def center_laser(self):
        self._model.laser_service.center_laser()

    def move_laser(self, x, y):
        # нельзя двигать лазер вручную во время сеанса трекинга
        if not self._model._tracker.in_progress:
            self._model.laser_service.move_laser(x, y)

    def left_button_click(self, selector, event):
        self._model.selecting_service.start_drawing_selected(selector)
        selector.left_button_click(Point(event.x, event.y))

    def left_button_down(self, selector, event):
        selector.left_button_down(Point(event.x, event.y))

    def left_button_up(self, selector, event):
        selector.left_button_up(Point(event.x, event.y))
        # TODO: привязывать события должен сам Selector
        # for event in MOUSE_EVENTS:
        #    self._root.unbind(event)

    def new_selection(self, name):
        # TODO: отрефакторить (надо бы перенести в модель)
        self._model.selecting_service.stop_drawing_selected(name)
        if OBJECT in name:
            area = self._model.get_or_create_selector(AREA)
            if not area.is_selected:
                self.show_message('Перед созданием объекта необходимо создать зону', 'Ошибка')
                return
        if AREA in name:
            self._model.selecting_service.stop_drawing_selected(OBJECT)
        self._model._tracker.in_progress = False
        selector = self._model.get_or_create_selector(name)

        binded_left_click = (LEFT_CLICK, partial(self.left_button_click, selector))
        binded_left_down = (LEFT_DOWN, partial(self.left_button_down, selector))
        binded_left_up = (LEFT_UP, partial(self.left_button_up, selector))
        event_callbacks = dict([binded_left_click, binded_left_down, binded_left_up])
        bindings = {}
        for event, callback, abstract_name in zip(MOUSE_EVENTS, event_callbacks.values(), event_callbacks.keys()):
            bindings[abstract_name] = partial(self._root.bind, event, callback)

        unbind_left_click = (LEFT_CLICK, partial(self._root.unbind, MOUSE_EVENTS[0]))
        unbind_left_down = (LEFT_DOWN, partial(self._root.unbind, MOUSE_EVENTS[1]))
        unbind_left_up = (LEFT_UP, partial(self._root.unbind, MOUSE_EVENTS[2]))
        unbindings = (unbind_left_click, unbind_left_down, unbind_left_up)

        selector.bind_events(bindings, unbindings)

    def calibrate_noise_threshold(self):
        # TODO: необходимо запоминать и восстанавливать старую область
        self._model.selecting_service.stop_drawing_selected(AREA)
        area = self._model.get_or_create_selector(AREA)
        width = self._view.window_width
        height = self._view.window_height
        area._points = [Point(0, 0), Point(height, 0), Point(height, width), Point(0, width)]
        area._sort_points_for_viewing()
        area.is_selected = True
        self._model.on_area_selected()
        self.new_selection(OBJECT)
        self._model.threshold_calibrator.in_progress = True
        Settings.NOISE_THRESHOLD = 0.0
        # TODO: Если до этого зона была выделена, то она должна восстановиться после калибровки

    def selector_is_selected(self, name):
        selector = self._model.selecting_service.get_or_create_selector(name)
        return selector.is_selected

    @staticmethod
    def show_message(message: str, title: str = ''):
        messagebox.showerror(title, message)

    @classmethod
    def show_fatal_exception(cls, e):
        # TODO: Возможно переместить во ViewModel
        cls.show_message(title='Фатальная ошибка. Работа программы будет продолжена, но может стать нестабильной',
                         message=f'{e}')
        logger.fatal(e)
