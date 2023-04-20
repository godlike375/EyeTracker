from copy import copy
from dataclasses import dataclass
from math import sqrt


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
        self = copy(self)
        if type(other) is Point:
            self.x *= other.x
            self.y *= other.y
        elif type(other) is float or type(other) is int:
            self.x *= other
            self.y *= other
        else:
            raise ValueError('incorrect right operand')
        return self

    def __truediv__(self, other):
        self = copy(self)
        if type(other) is Point:
            self.x /= other.x
            self.y /= other.y
        elif type(other) is float or type(other) is int:
            self.x /= other
            self.y /= other
        else:
            raise ValueError('incorrect right operand')
        return self

    def __add__(self, other):
        self = copy(self)
        if type(other) is Point:
            self.x += other.x
            self.y += other.y
        elif type(other) is float or type(other) is int:
            self.x += other
            self.y += other
        else:
            raise ValueError('incorrect right operand')
        return self

    def __abs__(self):
        return Point(abs(self.x), abs(self.y))

    def __ge__(self, other):
        return self.x >= other.x or self.y >= other.y

    def __lt__(self, other):
        return self.x < other.x or self.y < other.y

    def to_int(self):
        return Point(int(self.x), int(self.y))

    def __str__(self):
        return f'({self.x}, {self.y})'

    def __hash__(self):
        return hash((self.x, self.y))

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def calc_distance(self, other):
        return sqrt((other.x - self.x)**2 + (other.y - self.y)**2)

def calc_center(left_top: Point, right_bottom: Point) -> Point:
    return Point(int((left_top.x + right_bottom.x) / 2), int((left_top.y + right_bottom.y) / 2))
