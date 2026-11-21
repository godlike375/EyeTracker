from typing import List, Optional

from tracker.utils.coordinates import Point

MAX_AREA_POINTS = 4
MIN_DISTANCE_BETWEEN_POINTS = 5


class AreaSelector:
    def __init__(self):
        self._points: List[Point] = []

    @property
    def points(self) -> List[Point]:
        return list(self._points)

    @property
    def count(self) -> int:
        return len(self._points)

    @property
    def is_selecting(self) -> bool:
        return 0 < self.count < MAX_AREA_POINTS

    @property
    def is_complete(self) -> bool:
        return self.count == MAX_AREA_POINTS

    @property
    def is_valid(self) -> bool:
        if not self.is_complete:
            return False
        if len(set(self._points)) != MAX_AREA_POINTS:
            return False
        pairs = zip(self._points[:-1], self._points[1:])
        if any(a.calc_distance(b) < MIN_DISTANCE_BETWEEN_POINTS for a, b in pairs):
            return False
        first_last = self._points[0].calc_distance(self._points[-1])
        return first_last >= MIN_DISTANCE_BETWEEN_POINTS

    @property
    def last_point(self) -> Optional[Point]:
        return self._points[-1] if self._points else None

    def reset(self):
        self._points.clear()

    def add_point(self, point: Point) -> bool:
        if self.is_complete:
            return True
        self._points.append(point)
        return self.is_complete

    def nudge_last(self, dx: int, dy: int) -> bool:
        if not self._points:
            return False
        last = self._points[-1]
        self._points[-1] = Point(last.x + dx, last.y + dy)
        return True

    def to_tuples(self) -> List[tuple]:
        return [(int(p.x), int(p.y)) for p in self._points]
