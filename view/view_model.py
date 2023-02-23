from functools import partial
from tkinter import Tk, messagebox

from common.coordinates import Point
from common.logger import logger
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
        self._model.calibrate_laser()

    def center_laser(self):
        self._model.center_laser()

    def move_laser(self, x, y):
        self._model.move_laser(x, y)

    def left_button_click(self, selector, event):
        selector.left_button_click(Point(event.x, event.y))

    def left_button_down(self, selector, event):
        selector.left_button_down(Point(event.x, event.y))

    def left_button_up(self, selector, event):
        selector.left_button_up(Point(event.x, event.y))

    def new_selection(self, name, retry=False):
        selector = self._model.new_selection(name, retry)

        if selector is None:
            return

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
        self._model.selecting_service.start_drawing_selected(selector)

    def calibrate_noise_threshold(self):
        self._model.calibrate_noise_threshold(self._view.window_width, self._view.window_height)

    def selector_is_selected(self, name):
        selector = self._model.selecting_service.get_or_create_selector(name)
        return selector.is_selected

    def stop_tracking(self):
        self._model.stop_tracking()

    @staticmethod
    def show_message(message: str, title: str = ''):
        messagebox.showerror(title, message)

    @staticmethod
    def show_warning(message: str):
        messagebox.showerror('Предупреждение', message)

    @classmethod
    def show_fatal_exception(cls, e):
        cls.show_message(title='Фатальная ошибка. Работа программы будет продолжена, но может стать нестабильной',
                         message=f'{e}')
        logger.fatal(e)
