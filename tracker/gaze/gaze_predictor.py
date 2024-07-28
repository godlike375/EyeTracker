import sys
from multiprocessing import Process

import numpy as np
from PyQt6.QtWidgets import QApplication

from tracker.detectors.manager import DetectorsManager
from tracker.ui.calibration_window import CalibrationWindow
from tracker.utils.coordinates import Point, calc_center, get_translation_maxtix, translate_coordinates
from tracker.utils.fps import FPSLimiter
from tracker.utils.shared_objects import SharedVector, SharedFlag, SharedPoint

sys.path.append('../..')


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


def start_calibration(target_coordinates: SharedPoint, target_clicked: SharedFlag):
    app = QApplication(sys.argv)
    window = CalibrationWindow(target_coordinates, target_clicked)
    window.show()
    sys.exit(app.exec())


class GazePredictor:
    def __init__(self, gaze_coordinates: SharedPoint, detectors_manager: DetectorsManager):
        self.target_coordinates = SharedPoint('i', 0)
        self.target_clicked = SharedFlag()
        self.gaze_coordinates = gaze_coordinates
        self.detectors = detectors_manager

        self.gaze_origin = SharedVector('f', -1)
        self.gaze_direction = SharedVector('f', -1)

        self.calibration_window = Process(target=start_calibration,
                                          args=(self.target_coordinates, self.target_clicked),
                                          daemon=True)
        self.calibration_process = Process(target=self.calibrate, daemon=True)
        available = QApplication.screens()[-1].availableGeometry()
        self.screen_width = available.width()
        self.screen_height = available.height()

        self.calibration_process.start()
        self.calibration_window.start()

    def calibrate(self):
        fps = FPSLimiter(120)

        left_top = Point(0, 0)
        right_top = Point(self.screen_width, 0)
        right_bottom = Point(self.screen_width, self.screen_height)
        left_bottom = Point(0, self.screen_height)

        gaze_coords: list[Point] = [left_top, right_top, right_bottom, left_bottom]

        pupil_coords = []

        for coords in gaze_coords:
            self.target_coordinates.array[:] = coords.x, coords.y
            while not self.target_clicked:
                if not fps.able_to_execute():
                    fps.throttle()
                continue
            self.target_clicked.set(False)
            eye_left_top, eye_right_bottom = Point(*self.eye_coordinates[:2]), Point(*self.eye_coordinates[2:])
            eye_center = calc_center(eye_left_top, eye_right_bottom)
            # eye_width_height = eye_right_bottom - eye_left_top
            normalized_pupil = ((eye_center - Point(*self.pupil_coordinates[:])))  # / eye_width_height) * 25
            pupil_coords.append(normalized_pupil)

        pupil_to_gaze = get_translation_maxtix(pupil_coords, gaze_coords)

        while True:
            if not fps.able_to_execute():
                fps.throttle()
            eye_left_top, eye_right_bottom = Point(*self.eye_coordinates[:2]), Point(*self.eye_coordinates[2:])
            eye_center = calc_center(eye_left_top, eye_right_bottom)
            # eye_width_height = eye_right_bottom - eye_left_top
            normalized_pupil = ((eye_center - Point(*self.pupil_coordinates[:])) )  #/ eye_width_height) * 25
            predicted = translate_coordinates(pupil_to_gaze, normalized_pupil)
            self.gaze_coordinates.x = predicted.x
            self.gaze_coordinates.y = predicted.y

            self.target_coordinates.x = self.gaze_coordinates[0]
            self.target_coordinates.y = self.gaze_coordinates[1]


        # TODO: фактическое разрешение учитывать

