from functools import partial
from tkinter import Tk, END

from common.coordinates import Point
from model.selector import LEFT_CLICK, LEFT_DOWN, LEFT_UP
from common.settings import settings
from view import view_output

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

    def left_button_down_moved(self, selector, event):
        selector.left_button_down_moved(Point(event.x, event.y))

    def left_button_up(self, selector, event):
        selector.left_button_up(Point(event.x, event.y))

    def new_selection(self, name, retry=False):
        selector = self._model.new_selection(name, retry)

        if selector is None:
            return

        binded_left_click = (LEFT_CLICK, partial(self.left_button_click, selector))
        binded_left_down_moved = (LEFT_DOWN, partial(self.left_button_down_moved, selector))
        binded_left_up = (LEFT_UP, partial(self.left_button_up, selector))
        event_callbacks = dict([binded_left_click, binded_left_down_moved, binded_left_up])
        bindings = {}
        for event, callback, abstract_name in zip(MOUSE_EVENTS, event_callbacks.values(), event_callbacks.keys()):
            bindings[abstract_name] = partial(self._root.bind, event, callback)

        unbind_left_click = (LEFT_CLICK, partial(self._root.unbind, MOUSE_EVENTS[0]))
        unbind_left_down_moved = (LEFT_DOWN, partial(self._root.unbind, MOUSE_EVENTS[1]))
        unbind_left_up = (LEFT_UP, partial(self._root.unbind, MOUSE_EVENTS[2]))
        unbindings = (unbind_left_click, unbind_left_down_moved, unbind_left_up)

        selector.bind_events(bindings, unbindings)
        self._model.selecting_service.start_drawing(selector, name)

    def calibrate_noise_threshold(self):
        self._model.calibrate_noise_threshold(self._view.window_width, self._view.window_height)

    def selector_is_selected(self, name):
        return self._model.selecting_service.selector_is_selected(name)

    def cancel_active_process(self):
        self._model.cancel_active_process()

    def progress_bar_set_visibility(self, visible):
        self._view.progress_bar_set_visibility(visible)

    def progress_bar_set_value(self, val):
        self._view.progress_bar_set_value(val)

    def progress_bar_get_value(self):
        return self._view.progress_bar_get_value()

    def set_tip(self, tip):
        self._view.set_tip(f'Подсказка: {tip}')

    def save_settings(self, params):
        for name, text_edit in params.items():
            text_param = text_edit.get(0.0, END)[:-1]
            try:
                number_param = float(text_param) if '.' in text_param else int(text_param)
            except ValueError:
                view_output.show_warning(f'Некорректное значение параметра {name}:'
                                         f' ожидалось число, введено "{text_param}". Параметр не применён.')
            else:
                setattr(settings, name, number_param)
        view_output.show_warning('Большинство параметров будут применены после перезапуска программы.')

    def rotate_image(self, degree):
        self._model.rotate_image(degree)

    def flip_image(self, side):
        self._model.flip_image(side)

    def setup_window_geometry(self, reverse):
        self._view.setup_window_geometry(reverse)
