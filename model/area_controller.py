from common.coordinates import Point
from common.logger import logger


class AreaController:

    def __init__(self, min_xy, max_xy):
        # max resolution in abstract distance units
        self._resolution_xy = abs(min_xy - max_xy)
        self._left_top = None
        self._right_bottom = None
        self._length_xy = None
        self._dpi_xy = None

    @staticmethod
    def calc_center(xy: Point, xy2: Point) -> Point:
        return Point(int((xy.x + xy2.x) / 2), int((xy.y + xy2.y) / 2))

    def set_area(self, left_top: Point, right_bottom: Point):
        self._left_top = left_top
        self._right_bottom = right_bottom
        self._length_xy = Point(abs(left_top.x - right_bottom.x), abs(left_top.y - right_bottom.y))
        self._dpi_xy = Point(self._resolution_xy / self._length_xy.x, self._resolution_xy / self._length_xy.y)
        self.center = AreaController.calc_center(left_top, right_bottom)
        logger.debug(f'set area {left_top} {right_bottom}')

    def rect_intersected_borders(self, left_top: Point, right_bottom: Point) -> Point:
        return left_top.x < self._left_top.x or \
               right_bottom.x > self._right_bottom.x or \
               left_top.y < self._left_top.y or \
               right_bottom.y > self._right_bottom.y

    def calc_relative_coords(self, object_center: Point) -> Point:
        relative = object_center - self.center
        relative *= self._dpi_xy
        return relative
