from functools import partial
from tkinter import Tk, messagebox

from common.coordinates import Point
from common.settings import OBJECT

MOUSE_EVENTS = ('<B1-Motion>', '<Button-1>', '<ButtonRelease-1>')


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

    def selection_start(self, selector, event):
        self._model.start_drawing_selected(selector)
        selector.start(Point(event.x, event.y))

    def selection_progress(self, selector, event):
        selector.progress(Point(event.x, event.y))

    def selection_end(self, selector, event):
        selector.end(Point(event.x, event.y))
        for event in MOUSE_EVENTS:
            self._root.unbind(event)

    def new_selection(self, name):
        self._model.stop_drawing_selected(OBJECT)
        self._model.stop_drawing_selected(name)
        self._model._tracker.in_progress = False
        selector = self._model.get_or_create_selector(name)
        binded_progress = partial(self.selection_progress, selector)
        binded_start = partial(self.selection_start, selector)
        binded_end = partial(self.selection_end, selector)
        event_callbacks = (binded_progress, binded_start, binded_end)
        for event, callback in zip(MOUSE_EVENTS, event_callbacks):
            self._root.bind(event, callback)

    def selector_is_selected(self, name):
        selector = self._model.get_or_create_selector(name)
        return selector.is_selected()

    @staticmethod
    def show_message(message: str, title: str = ''):
        messagebox.showerror(title, message)
