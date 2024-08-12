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


def plane_from_points(points):
    """
    Вычисляет уравнение плоскости по 4 точкам.
    Возвращает коэффициенты A, B, C, D уравнения Ax + By + Cz + D = 0
    """
    p1, p2, p3 = points
    v1 = p2 - p1
    v2 = p3 - p1
    normal = np.cross(v1, v2)
    A, B, C = normal
    D = -np.dot(normal, p1)
    return A, B, C, D


def center_of_points(points):
    """Вычисляет центр множества точек"""
    return np.mean(points, axis=0)


def ray_end_point(points, distance, center):
    """
    Вычисляет конечную точку луча, ортогонального центру плоскости,
    на заданном расстоянии
    """
    # Вычисляем уравнение плоскости
    A, B, C, D = plane_from_points(points)
    normal = np.array([A, B, C])

    # Нормализуем вектор нормали
    normal_unit = normal / np.linalg.norm(normal)

    # Вычисляем конечную точку луча
    end_point = center + distance * normal_unit

    return end_point


def closest_points_between_rays(O1: np.ndarray, D1: np.ndarray,
                                O2: np.ndarray, D2: np.ndarray):
    """
    Находит ближайшие точки между двумя лучами и их середину.

    :param O1: Начальная точка первого луча
    :param D1: Направляющий вектор первого луча
    :param O2: Начальная точка второго луча
    :param D2: Направляющий вектор второго луча
    :return: Точку между двумя ближайшими точками на лучах
    """
    # Строим матрицу системы
    A = np.array([D1, -D2]).T
    b = O2 - O1

    # Решаем систему уравнений методом наименьших квадратов
    t1, t2 = np.linalg.lstsq(A, b, rcond=None)[0]

    # Находим ближайшие точки на каждом луче
    P1 = O1 + t1 * D1
    P2 = O2 + t2 * D2

    # Находим середину между этими точками
    midpoint = (P1 + P2) / 2

    return midpoint