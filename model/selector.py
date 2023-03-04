from abc import ABC

from common.coordinates import Point, RectBased
from common.logger import logger
from view.drawing import Drawable, Processor

LEFT_CLICK = 'left_click'
LEFT_DOWN = 'left_down'
LEFT_UP = 'left_up'
MIN_DISTANCE_BETWEEN_POINTS = 28
MIN_POINTS_SELECTED = 2
EVENT_NAME = 1


class Selector(ABC):
    def __init__(self, name: str, callback, points: tuple = None):
        super().__init__()
        self.name = name
        self._after_selection = callback
        self._selected = False
        self._points = list(points) if points else []
        self._unbindings = []

    def left_button_click(self, event):
        self._points.append(Point(event.x, event.y))

    def left_button_down_moved(self, event):
        ...

    def left_button_up(self, event):
        ...

    @property
    def is_selected(self):
        return self._selected and not self.is_empty

    @is_selected.setter
    def is_selected(self, selected):
        if type(selected) is bool:
            self._selected = selected
        else:
            raise NotImplementedError('assigned data type is not bool')

    @property
    def is_empty(self):
        if len(self._points) < MIN_POINTS_SELECTED:
            return True
        distances = [i.calc_distance(j) for i, j in zip(self._points[:-1], self._points[1:])]
        less_than_min_dist = any([i < MIN_DISTANCE_BETWEEN_POINTS for i in distances])
        return len(set(self._points)) != len(self._points) or less_than_min_dist

    def _sort_points_for_viewing(self):
        # FIXME: если трапецию сбоку рисовать с широким основанием, то багует или же ромб
        half_points = len(self._points) // 2
        sorted_points = sorted(self._points, key=lambda p: p.x + p.y * 2)
        self._points = sorted_points[:half_points] + \
            sorted(sorted_points[half_points:], key=lambda p: p.x * 2 + p.y, reverse=True)

    def bind_events(self, events, unbindings):
        self._unbindings = unbindings

    def finish_selecting(self):
        self._selected = True
        self._sort_points_for_viewing()
        for unbind in self._unbindings:
            unbind[EVENT_NAME]()
        if self._after_selection is not None:
            self._after_selection()

    def cancel_selecting(self):
        if self._selected:
            # Отменить можно только то, что не до конца выделено
            return
        self._selected = False
        self._points.clear()
        for unbind in self._unbindings:
            unbind[EVENT_NAME]()


class ObjectSelector(RectBased, Drawable, Selector):
    MAX_POINTS = 2

    def __init__(self, name: str, callback, points=None):
        super().__init__(name, callback, points)
        self._selected = False
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

    def left_button_click(self, event):
        self._points = [Point(event.x, event.y)]
        # BUG: Баг с событиями: если много раз выделять пустой объект (просто кликать по экрану),
        # то очередь событий ломается и может клик сработать несколько раз
        self._left_top.x, self._left_top.y = event.x, event.y
        logger.debug(f'start selecting {event.x, event.y}')

    def left_button_down_moved(self, event):
        self._right_bottom.x, self._right_bottom.y = event.x, event.y

    def left_button_up(self, event):
        logger.debug(f'end selecting {self.name} {event.x, event.y}')
        self._points.append(Point(event.x, event.y))
        points_count = len(self._points)
        # Условие относится к багу, описанному выше. Такие невалидные состояния отметаем
        if points_count < ObjectSelector.MAX_POINTS:
            return
        self._left_top, self._right_bottom = self._points
        self.finish_selecting()

    def draw_on_frame(self, frame):
        return Processor.draw_rectangle(frame, self._left_top, self._right_bottom)

    def bind_events(self, event_bindings, unbindings):
        super().bind_events(event_bindings, unbindings)
        for bind in event_bindings.values():
            bind()

    @property
    def is_empty(self):
        ltx, lty, rbx, rby = *self._left_top, *self._right_bottom
        return ltx == rbx or lty == rby or\
            abs(ltx - rbx) < MIN_DISTANCE_BETWEEN_POINTS or\
            abs(lty - rby) < MIN_DISTANCE_BETWEEN_POINTS or\
            super().is_empty


class AreaSelector(Drawable, Selector):
    MAX_POINTS = 4

    def __init__(self, name: str, callback, points=None):
        super().__init__(name, callback, points)
        self._current_point_number = 0

    def left_button_click(self, event):
        logger.debug(f'selecting {self._current_point_number} point at {event.x, event.y}')

        if self._current_point_number < AreaSelector.MAX_POINTS:
            super().left_button_click(event)
        self._current_point_number += 1
        if self._current_point_number == AreaSelector.MAX_POINTS:
            self.finish_selecting()

    def draw_on_frame(self, frame):
        if not self._selected:
            for point in self._points:
                frame = Processor.draw_circle(frame, point)
        else:
            for a, b in zip(self._points[:-1], self._points[1:]):
                frame = Processor.draw_line(frame, a, b)
            frame = Processor.draw_line(frame, self._points[-1], self._points[0])
        return frame

    def bind_events(self, event_bindings, unbindings):
        super().bind_events(event_bindings, unbindings)
        event_bindings[LEFT_CLICK]()

    @property
    def points(self):
        return self._points
