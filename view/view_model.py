from functools import partial
from tkinter import Tk, messagebox

from common.coordinates import Point
from common.settings import OBJECT
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
        self._model.start_drawing_selected(selector)
        selector.left_button_click(Point(event.x, event.y))

    def left_button_down(self, selector, event):
        selector.left_button_down(Point(event.x, event.y))

    def left_button_up(self, selector, event):
        selector.left_button_up(Point(event.x, event.y))
        # TODO: привязывать события должен сам Selector
        # for event in MOUSE_EVENTS:
        #    self._root.unbind(event)

    def new_selection(self, name):
        # TODO: отрефакторить
        self._model.stop_drawing_selected(name)
        if 'area' in name:
            self._model.stop_drawing_selected(OBJECT)
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

    def selector_is_selected(self, name):
        selector = self._model.get_or_create_selector(name)
        return selector.is_selected

    @staticmethod
    def show_message(message: str, title: str = ''):
        messagebox.showerror(title, message)
