from typing import Callable, List, Optional

import numpy as np

from tracker.utils.coordinates import Point, get_translation_maxtix, translate_coordinates

from .laser_controller import DEFAULT_MAX_LASER_RANGE


class AreaController:
    def __init__(self,
                 min_xy: int = -DEFAULT_MAX_LASER_RANGE,
                 max_xy: int = DEFAULT_MAX_LASER_RANGE,
                 on_out_of_area: Optional[Callable[[bool], None]] = None):
        self._min_xy = Point(min_xy, min_xy)
        self._max_xy = Point(max_xy, max_xy)
        self._translation_matrix = None
        self._inverse_matrix = None
        self._area_points = None
        self._on_out_of_area = on_out_of_area

    @property
    def is_set(self) -> bool:
        return self._translation_matrix is not None

    @property
    def area_points(self) -> Optional[List[Point]]:
        return self._area_points

    def set_area(self, screen_points: List[Point], laser_borders: List[Point]):
        if len(screen_points) != 4 or len(laser_borders) != 4:
            raise ValueError('area requires exactly 4 screen points and 4 laser borders')
        self._area_points = list(screen_points)
        self._translation_matrix = get_translation_maxtix(screen_points, laser_borders)
        self._inverse_matrix = np.linalg.inv(self._translation_matrix)

    def clear(self):
        self._translation_matrix = None
        self._inverse_matrix = None
        self._area_points = None

    def point_is_out_of_area(self, point: Point, beep_sound_allowed: bool = False) -> bool:
        if not self.is_set:
            return False
        translated = translate_coordinates(self._translation_matrix, point)
        out_of_area = (translated.x < self._min_xy.x or translated.x > self._max_xy.x
                       or translated.y < self._min_xy.y or translated.y > self._max_xy.y)
        if beep_sound_allowed and self._on_out_of_area is not None:
            self._on_out_of_area(out_of_area)
        return out_of_area

    def calc_laser_coords(self, object_center: Point) -> Point:
        if not self.is_set:
            return object_center
        return translate_coordinates(self._translation_matrix, object_center)

    def calc_screen_coords(self, laser_point: Point) -> Optional[Point]:
        if not self.is_set:
            return None
        return translate_coordinates(self._inverse_matrix, laser_point)
