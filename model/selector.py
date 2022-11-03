import logging

from common.utils import Point, LOGGER_NAME
from model.frame_processing import Processor, FramePipeline

logger = logging.getLogger(LOGGER_NAME)


class Selector:
    def __init__(self, name: str, pipeline: FramePipeline, callback):
        self._name = name
        self._pipeline = pipeline
        self.left_top = Point(0, 0)
        self.right_bottom = Point(0, 0)
        self._callback = callback
        self._selected = False

    def start(self, event):
        logger.debug(f'start selecting {event.x, event.y}')
        self._pipeline.append(self.draw_selected_rect)
        self.left_top.x, self.left_top.y = event.x, event.y

    def progress(self, event):
        self.right_bottom.x, self.right_bottom.y = event.x, event.y

    def end(self, event):
        logger.debug(f'end selecting {event.x, event.y}')
        self.right_bottom.x, self.right_bottom.y = event.x, event.y
        self.left_top.x, self.right_bottom.x = Selector.check_swap_coords(self.left_top.x, self.right_bottom.x)
        self.left_top.y, self.right_bottom.y = Selector.check_swap_coords(self.left_top.y, self.right_bottom.y)
        self._selected = True
        self._callback(self._name)

    def is_selected(self):
        return self._selected

    def draw_selected_rect(self, frame):
        rect_frame = Processor.draw_rectangle(frame, self.left_top, self.right_bottom)
        return rect_frame

    def is_empty(self):
        return self.area_selector.left_top == self.area_selector.right_bottom

    @staticmethod
    def check_swap_coords(x1: int, x2: int):
        return (x2, x1) if x2 <= x1 else (x1, x2)
