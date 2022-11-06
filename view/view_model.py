from functools import partial
from tkinter import Tk, messagebox

from common.coordinates import Point


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
        self._model._calibrate_laser()

    def center_laser(self):
        self._model.center_laser()

    def selection_start(self, selector, event):
        self._model.add_selector_pipeline(selector)
        selector.start(Point(event.x, event.y))

    def selection_progress(self, selector, event):
        selector.progress(Point(event.x, event.y))

    def selection_end(self, selector, event):
        selector.end(Point(event.x, event.y))
        self._root.unbind('<B1-Motion>')
        self._root.unbind('<Button-1>')
        self._root.unbind('<ButtonRelease-1>')

    def start_selection(self, name):
        # TODO: Починить логику, там в пайплайн добавляются строки
        self._model.remove_processor(name)
        selector = self._model.get_selector(name)
        binded_progress = partial(self.selection_progress, selector)
        binded_start = partial(self.selection_start, selector)
        binded_end = partial(self.selection_end, selector)
        self._root.bind('<B1-Motion>', binded_progress)
        self._root.bind('<Button-1>', binded_start)
        self._root.bind('<ButtonRelease-1>', binded_end)

    def selector_is_selected(self, name):
        selector = self._model.get_selector(name)
        return selector.is_selected()

    def show_message(self, message: str, title: str = ''):
        messagebox.showerror(title, message)
