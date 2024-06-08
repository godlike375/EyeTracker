from abc import ABC
from typing import Callable

import cv2

from tracker.utils.coordinates import Point
from tracker.abstractions import RectBased, DrawnObject, ProcessBased
from tracker.utils.logger import logger
from eye_tracker.view.drawing import Processor

LEFT_CLICK = 'left_click'
LEFT_DOWN = 'left_down'
LEFT_UP = 'left_up'
MIN_DISTANCE_BETWEEN_POINTS = 5
MIN_POINTS_SELECTED = 2
EVENT_NAME = 1
POINTS_ORIENTATION = ['TL', 'TR', 'BR', 'BL']
CORRECTIVE_STEP_PIXELS = 1


class Selector(ProcessBased):
    def __init__(self, callback: Callable, points: tuple = None):
        ProcessBased.__init__(self)
        self._after_selection = callback
        self._points = list(points) if points else []
        self._unbind_callback: Callable = None
        self.left_top = Point(0, 0)
        self.right_bottom = Point(0, 0)

    def left_button_click(self, coordinates):
        self._points.append(coordinates)

    def left_button_down_moved(self, event):
        ...

    def left_button_up(self, event):
        ...

    @property
    def is_done(self):
        return not self.in_progress and super().is_done and not self.is_empty

    @property
    def is_empty(self):
        if len(self._points) < MIN_POINTS_SELECTED:
            return True
        distances = [i.calc_distance(j) for i, j in zip(self._points[:-1], self._points[1:])]
        less_than_min_dist = any([i < MIN_DISTANCE_BETWEEN_POINTS for i in distances])
        return len(set(self._points)) != len(self._points) or less_than_min_dist

    def finish_selecting(self, event):
        self.left_button_up(event)
        self.finish()
        #self._unbind_callback()
        if self._after_selection is not None:
            self._after_selection(self)

    def cancel(self):
        if not self.in_progress:
            return
        self._points.clear()
        self._unbind_callback()
        ProcessBased.cancel(self)

    def calculate_correct_square_points(self):
        xs = sorted([p.x for p in self._points])
        ys = sorted([p.y for p in self._points])

        return [Point(xs[0], ys[0]), Point(xs[-1], ys[-1])]


class EyeSelector(DrawnObject, Selector):
    MAX_POINTS = 2

    def __init__(self, name: str, unbind, on_finished, points=None):
        DrawnObject.__init__(self, name)
        Selector.__init__(self, on_finished, points)
        self._unbind_callback = unbind

    def left_button_click(self, coordinates):
        super().left_button_click(coordinates)
        # BUG: Баг с событиями: если много раз выделять пустой объект (просто кликать по экрану),
        # то очередь событий ломается и может клик сработать несколько раз
        self.left_top.x, self.left_top.y = coordinates.x, coordinates.y
        logger.debug(f'start selecting {coordinates.x, coordinates.y}')

    def left_button_down_moved(self, event):
        self.right_bottom = event

    def left_button_up(self, event):
        logger.debug(f'end selecting {self.name} {event.x, event.y}')
        self._points.append(event)
        points_count = len(self._points)
        # BUG: Условие относится к багу, описанному выше. Такие невалидные состояния отметаем
        if points_count < EyeSelector.MAX_POINTS:
            self._points.clear()
            return
        elif points_count > EyeSelector.MAX_POINTS:
            self._points = self._points[points_count - EyeSelector.MAX_POINTS:]
        self._points = self.calculate_correct_square_points()
        self.left_top, self.right_bottom = self._points
        # WARNING: не вызывать здесь self.finish_selecting(), т.к. он вызывается в arrow_press() view_model

    def arrow_up(self):
        self.left_top.y -= CORRECTIVE_STEP_PIXELS
        self.right_bottom.y -= CORRECTIVE_STEP_PIXELS

    def arrow_down(self):
        self.left_top.y += CORRECTIVE_STEP_PIXELS
        self.right_bottom.y += CORRECTIVE_STEP_PIXELS

    def arrow_left(self):
        self.left_top.x -= CORRECTIVE_STEP_PIXELS
        self.right_bottom.x -= CORRECTIVE_STEP_PIXELS

    def arrow_right(self):
        self.left_top.x += CORRECTIVE_STEP_PIXELS
        self.right_bottom.x += CORRECTIVE_STEP_PIXELS

    def draw_on_frame(self, frame):
        return cv2.rectangle(frame, (*self.left_top,), (*self.right_bottom,),
                          (255, 0, 224), 2)

    @property
    def is_empty(self):
        ltx, lty, rbx, rby = *self.left_top, *self.right_bottom
        return ltx == rbx or lty == rby or \
               abs(ltx - rbx) < MIN_DISTANCE_BETWEEN_POINTS or \
               abs(lty - rby) < MIN_DISTANCE_BETWEEN_POINTS or \
               super().is_empty
