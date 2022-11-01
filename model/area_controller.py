from common.utils import Point


class AreaController:

    def __init__(self, min_xy, max_xy):
        self.min_xy = min_xy
        self.max_xy = max_xy
        # max resolution in abstract distance units
        self.resolution_xy = abs(min_xy - max_xy)
        self.left_top = None
        self.right_bottom = None
        self.length_xy = None
        self.dpi_xy = None

    @staticmethod
    def calc_center(xy: Point, xy2: Point) -> Point:
        return Point(int((xy.x + xy2.x) / 2), int((xy.y + xy2.y) / 2))

    def set_area(self, left_top: Point, right_bottom: Point) -> Point:
        self.left_top = left_top
        self.right_bottom = right_bottom
        self.length_xy = Point(abs(left_top.x - right_bottom.x), abs(left_top.y - right_bottom.y))
        self.dpi_xy = Point(self.resolution_xy / self.length_xy.x, self.resolution_xy / self.length_xy.y)
        self.center = AreaController.calc_center(left_top, right_bottom)

    def rect_intersected_borders(self, left_top: Point, right_bottom: Point) -> Point:
        if left_top.x < self.left_top.x or \
                right_bottom.x > self.right_bottom.x or \
                left_top.y < self.left_top.y or \
                right_bottom.y > self.right_bottom.y:
            return True
        return False

    def calc_relative_coords(self, object_center: Point) -> Point:
        relative = object_center - self.center
        relative *= self.dpi_xy
        return relative
