import numpy as np

from tracker.utils.coordinates import Point


def new_axis_relative_point_cords(nx1: Point, nx2: Point, ny1: Point, ny2: Point, point: Point):
    # Начальные координаты отрезков
    x1, y1 = nx1
    x2, y2 = nx2
    u1, v1 = ny1
    u2, v2 = ny2

    # Координаты точки (a, b)
    a, b = point

    # Векторы новых осей
    X_vector = np.array([x2 - x1, y2 - y1])
    Y_vector = np.array([u2 - u1, v2 - v1])

    # Нормализация векторов
    X_unit = X_vector / np.linalg.norm(X_vector)
    Y_unit = Y_vector / np.linalg.norm(Y_vector)

    # Матрица перехода
    T = np.array([X_unit, Y_unit]).T

    # Координаты точки относительно нового начала координат
    point = np.array([a - x1, b - y1])

    # Новые координаты
    relative_target_coords = np.linalg.solve(T, point)
    return relative_target_coords

new_axis_relative_point_cords(Point(0, 0), Point(1, 1), Point(0, 0), Point(1, -1), Point(0.5, 0.5))