from multiprocessing import Array, Value

from tracker.utils.coordinates import calc_center, Point, BoundingBox

INVALID_VALUE = -1


class SharedPoint:
    def __init__(self, type: str = 'i', initial_value = INVALID_VALUE):
        self.array = Array(type, [initial_value] * 2)

    def invalidate(self):
        self.array[:] = INVALID_VALUE, INVALID_VALUE

    @property
    def x(self):
        return self.array[0]

    @x.setter
    def x(self, value):
        self.array[0] = value

    @property
    def y(self):
        return self.array[1]

    @y.setter
    def y(self, value):
        self.array[1] = value

    @property
    def is_valid(self):
        return self.x != INVALID_VALUE and self.y != INVALID_VALUE

    def __add__(self, other):
        return Point(self.x + other.x, self.y + other.y)


class SharedVector:
    def __init__(self, type: str = 'f', initial_value = INVALID_VALUE):
        self.array = Array(type, [initial_value] * 3)

    def invalidate(self):
        self.array[:] = INVALID_VALUE, INVALID_VALUE, INVALID_VALUE

    @property
    def x(self):
        return self.array[0]

    @x.setter
    def x(self, value):
        self.array[0] = value

    @property
    def y(self):
        return self.array[1]

    @y.setter
    def y(self, value):
        self.array[1] = value

    @property
    def z(self):
        return self.array[2]

    @z.setter
    def z(self, value):
        self.array[2] = value

    def calc_distance(self, another: SharedPoint):
        return Point(self.x, self.y).calc_distance(another)

    @property
    def is_valid(self):
        return self.x != INVALID_VALUE and self.y != INVALID_VALUE and self.z != INVALID_VALUE

    def to_point(self) -> Point:
        return Point(self.x, self.y)


class SharedBox:
    def __init__(self, type: str = 'i', initial_value = INVALID_VALUE):
        self.left_top = SharedPoint(type, initial_value)
        self.right_bottom = SharedPoint(type, initial_value)

    @property
    def center(self):
        return calc_center(self.left_top, self.right_bottom)

    def invalidate(self):
        self.left_top.invalidate()
        self.right_bottom.invalidate()

    def __iter__(self):
        return iter((self.left_top.x, self.left_top.y, self.right_bottom.x, self.right_bottom.y))

    @property
    def x1(self):
        return self.left_top.x

    @x1.setter
    def x1(self, value):
        self.left_top.x = value

    @property
    def x2(self):
        return self.right_bottom.x

    @x2.setter
    def x2(self, value):
        self.right_bottom.x = value

    @property
    def y1(self):
        return self.left_top.y

    @y1.setter
    def y1(self, value):
        self.left_top.y = value

    @property
    def y2(self):
        return self.right_bottom.y

    @y2.setter
    def y2(self, value):
        self.right_bottom.y = value

    def is_valid(self):
        return self.left_top.is_valid and self.right_bottom.is_valid

    def __add__(self, other: Point):
        return BoundingBox(*(self.left_top+other), *(self.right_bottom+other))


class SharedFlag:
    def __init__(self, initial_value: bool = False):
        self.flag = Value('b', initial_value)


    def __bool__(self):
        return bool(self.flag.value)

    def get(self):
        return bool(self)

    def set(self, value: bool):
        self.flag.value = value
