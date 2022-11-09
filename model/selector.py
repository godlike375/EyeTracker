import logging

from common.thread_helpers import LOGGER_NAME
from common.coordinates import Point, RectBased

logger = logging.getLogger(LOGGER_NAME)


class Selector(RectBased):
    def __init__(self, name: str, callback):
        super().__init__()
        self.name = name
        self._callback = callback
        self._selected = False
        self._left_top = Point(0, 0)
        self._right_bottom = Point(0, 0)

    @property
    def left_top(self):
        return self._left_top

    @property
    def right_bottom(self):
        return self._right_bottom

    def start(self, event):
        logger.debug(f'start selecting {event.x, event.y}')
        self._left_top.x, self._left_top.y = event.x, event.y

    def progress(self, event):
        self._right_bottom.x, self._right_bottom.y = event.x, event.y

    def end(self, event):
        logger.debug(f'end selecting {self.name} {event.x, event.y}')
        self._right_bottom.x, self._right_bottom.y = event.x, event.y
        self._left_top.x, self._right_bottom.x = Selector.check_swap_coords(self._left_top.x, self._right_bottom.x)
        self._left_top.y, self._right_bottom.y = Selector.check_swap_coords(self._left_top.y, self._right_bottom.y)
        self._selected = True
        self._callback()

    def is_selected(self):
        return self._selected

    def is_empty(self):
        return self._left_top == self._right_bottom

    @staticmethod
    def check_swap_coords(x1: int, x2: int):
        return (x2, x1) if x2 <= x1 else (x1, x2)
