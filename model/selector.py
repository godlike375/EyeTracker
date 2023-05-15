from abc import ABC

from common.coordinates import Point
from common.abstractions import RectBased, Drawable, Cancellable, ProcessBased
from common.logger import logger
from view.drawing import Processor

LEFT_CLICK = 'left_click'
LEFT_DOWN = 'left_down'
LEFT_UP = 'left_up'
MIN_DISTANCE_BETWEEN_POINTS = 20
MIN_POINTS_SELECTED = 2
EVENT_NAME = 1
POINTS_ORIENTATION = ['TL', 'TR', 'BR', 'BL']
CORRECTIVE_STEP_PIXELS = 1


class Selector(Cancellable, ABC, ProcessBased):
    def __init__(self, name: str, callback, points: tuple = None):
        ProcessBased.__init__(self)
        self.name = name
        self._after_selection = callback
        self._points = list(points) if points else []
        self._unbindings = []

    def left_button_click(self, coordinates):
        self.start()
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

    def _sort_points_for_viewing(self):
        half_points = len(self._points) // 2
        sorted_by_y = sorted(self._points, key=lambda p: p.y, reverse=False)
        top_points = sorted_by_y[:half_points]
        bottom_points = sorted_by_y[half_points:]
        top_points.sort(key=lambda p: p.x)
        bottom_points.sort(key=lambda p: p.x, reverse=True)
        self._points = top_points + bottom_points

    def bind_events(self, events, unbindings):
        self._unbindings = unbindings

    def finish_selecting(self):
        self.finish()
        for unbind in self._unbindings:
            unbind[EVENT_NAME]()
        if self._after_selection is not None:
            self._after_selection()

    def cancel(self):
        if not self.in_progress:
            return
        super().cancel()
        self._points.clear()
        for unbind in self._unbindings:
            unbind[EVENT_NAME]()


class ObjectSelector(RectBased, Drawable, Selector):
    MAX_POINTS = 2

    def __init__(self, name: str, callback, points=None):
        Selector.__init__(self, name, callback, points)
        self._left_top = Point(0, 0)
        self._right_bottom = Point(0, 0)

    @property
    def left_top(self):
        return self._left_top

    @property
    def right_bottom(self):
        return self._right_bottom

    @left_top.setter
    def left_top(self, value):
        self._left_top = value

    @right_bottom.setter
    def right_bottom(self, value):
        self._right_bottom = value

    def left_button_click(self, coordinates):
        super().left_button_click(coordinates)
        # BUG: Баг с событиями: если много раз выделять пустой объект (просто кликать по экрану),
        # то очередь событий ломается и может клик сработать несколько раз
        self._left_top.x, self._left_top.y = coordinates.x, coordinates.y
        logger.debug(f'start selecting {coordinates.x, coordinates.y}')

    def left_button_down_moved(self, event):
        self._right_bottom.x, self._right_bottom.y = event.x, event.y

    def left_button_up(self, event):
        logger.debug(f'end selecting {self.name} {event.x, event.y}')
        self._points.append(event)
        points_count = len(self._points)
        # BUG: Условие относится к багу, описанному выше. Такие невалидные состояния отметаем
        if points_count < ObjectSelector.MAX_POINTS:
            self._points.clear()
            return
        elif points_count > ObjectSelector.MAX_POINTS:
            self._points = self._points[points_count - ObjectSelector.MAX_POINTS:]
        self._sort_points_for_viewing()
        self._left_top, self._right_bottom = self._points
        self.finish_selecting()

    def arrow_up(self):
        self._left_top.y -= CORRECTIVE_STEP_PIXELS
        self._right_bottom.y -= CORRECTIVE_STEP_PIXELS

    def arrow_down(self):
        self._left_top.y += CORRECTIVE_STEP_PIXELS
        self._right_bottom.y += CORRECTIVE_STEP_PIXELS

    def arrow_left(self):
        self._left_top.x -= CORRECTIVE_STEP_PIXELS
        self._right_bottom.x -= CORRECTIVE_STEP_PIXELS

    def arrow_right(self):
        self._left_top.x += CORRECTIVE_STEP_PIXELS
        self._right_bottom.x += CORRECTIVE_STEP_PIXELS

    def draw_on_frame(self, frame):
        return Processor.draw_rectangle(frame, self._left_top, self._right_bottom)

    def bind_events(self, event_bindings, unbindings):
        super().bind_events(event_bindings, unbindings)
        for bind in event_bindings.values():
            bind()

    @property
    def is_empty(self):
        ltx, lty, rbx, rby = *self._left_top, *self._right_bottom
        return ltx == rbx or lty == rby or \
               abs(ltx - rbx) < MIN_DISTANCE_BETWEEN_POINTS or \
               abs(lty - rby) < MIN_DISTANCE_BETWEEN_POINTS or \
               super().is_empty


class AreaSelector(Drawable, Selector):
    MAX_POINTS = 4

    def __init__(self, name: str, callback, points=None):
        super().__init__(name, callback, points)
        self._current_point_number = 0
        Processor.load_color()

    def left_button_click(self, coordinates):
        logger.debug(f'selecting {self._current_point_number} point at {coordinates.x, coordinates.y}')

        if self._current_point_number < AreaSelector.MAX_POINTS:
            super().left_button_click(coordinates)
        self._current_point_number += 1
        if self._current_point_number == AreaSelector.MAX_POINTS:
            self.finish_selecting()

    def draw_on_frame(self, frame):
        if self.in_progress:
            for point in self._points:
                frame = Processor.draw_circle(frame, point)
        elif self.is_done:
            for a, b in zip(self._points[:-1], self._points[1:]):
                frame = Processor.draw_line(frame, a, b)
            frame = Processor.draw_line(frame, self._points[-1], self._points[0])

        for point, name in zip(self._points, POINTS_ORIENTATION):
            frame = Processor.draw_text(frame, name, point)
        return frame

    def bind_events(self, event_bindings, unbindings):
        super().bind_events(event_bindings, unbindings)
        event_bindings[LEFT_CLICK]()

    @property
    def points(self):
        return self._points
