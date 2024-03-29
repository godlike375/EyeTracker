from dataclasses import dataclass
from math import sqrt
from typing import List

import cv2
import numpy as np


@dataclass
class Point:
    __slots__ = ['x', 'y']
    x: float
    y: float

    def __iter__(self):
        return iter((self.x, self.y))

    def __sub__(self, other):
        return Point(self.x - other.x, self.y - other.y)

    def __imul__(self, other):
        if type(other) is Point:
            self.x *= other.x
            self.y *= other.y
        elif type(other) is float or type(other) is int:
            self.x *= other
            self.y *= other
        else:
            raise ValueError('incorrect right operand')
        return self

    def __mul__(self, other):
        if type(other) is Point:
            return Point(self.x * other.x, self.y * other.y)
        elif type(other) is float or type(other) is int:
            return Point(self.x * other, self.y * other)
        else:
            raise ValueError('incorrect right operand')

    def __truediv__(self, other):
        if type(other) is Point:
            return Point(self.x / other.x, self.y / other.y)
        elif type(other) is float or type(other) is int:
            return Point(self.x / other, self.y / other)
        else:
            raise ValueError('incorrect right operand')

    def __floordiv__(self, other):
        if type(other) is Point:
            return Point(self.x // other.x, self.y // other.y)
        elif type(other) is int:
            return Point(self.x // other, self.y // other)
        else:
            raise ValueError('incorrect right operand')

    def __add__(self, other):
        if type(other) is Point:
            return Point(self.x + other.x, self.y + other.y)
        elif type(other) is float or type(other) is int:
            return Point(self.x + other, self.y + other)
        else:
            raise ValueError('incorrect right operand')

    def __abs__(self):
        return Point(abs(self.x), abs(self.y))

    def __ge__(self, other):
        if type(other) is Point:
            return self.x >= other.x or self.y >= other.y
            # or сделано для триггера на две оси перемещения в трекере
        elif type(other) is float or type(other) is int:
            return self.x >= other or self.y >= other
        else:
            raise ValueError('incorrect right operand')

    def __lt__(self, other):
        if type(other) is Point:
            return self.x < other.x or self.y < other.y
        elif type(other) is float or type(other) is int:
            return self.x < other or self.y < other
        else:
            raise ValueError('incorrect right operand')

    def to_int(self):
        return Point(int(self.x), int(self.y))

    def __str__(self):
        return f'({self.x}, {self.y})'

    def __hash__(self):
        return hash((self.x, self.y))

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def calc_distance(self, other):
        return sqrt((other.x - self.x) ** 2 + (other.y - self.y) ** 2)


def calc_center(left_top: Point, right_bottom: Point) -> Point:
    return Point(int((left_top.x + right_bottom.x) / 2), int((left_top.y + right_bottom.y) / 2))


def transform_points_array(array: List[Point]):
    return np.array([(*p,) for p in array], dtype="float32")
    # TODO: вынести в отдельные функции и встроить автокоррекцию координат в CropZoomer


def get_translation_maxtix(source_points: List[Point], target_points: List[Point]):
    # https://theailearner.com/tag/cv2-getperspectivetransform/
    source_points_array = transform_points_array(source_points)
    target_points_array = transform_points_array(target_points)
    return cv2.getPerspectiveTransform(source_points_array, target_points_array)

def get_translation_maxtix_between_resolutions(old_width: int, old_height: int, new_width: int, new_height: int):
    source_points = [Point(0, 0), Point(old_width, 0), Point(old_width, old_height), Point(0, old_height)]
    target_points = [Point(0, 0), Point(new_width, 0), Point(new_width, new_height), Point(0, new_height)]
    return get_translation_maxtix(source_points, target_points)

def translate_coordinates(translation_matrix, point: Point):
    m = translation_matrix
    x = point.x
    y = point.y
    common_denominator = (m[2, 0] * x + m[2, 1] * y + m[2, 2])
    X = (m[0, 0] * x + m[0, 1] * y + m[0, 2]) / common_denominator
    Y = (m[1, 0] * x + m[1, 1] * y + m[1, 2]) / common_denominator
    return Point(int(X), int(Y))
