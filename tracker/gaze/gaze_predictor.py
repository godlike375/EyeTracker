import sys
import time
from multiprocessing import Process

import numpy as np
from PyQt6.QtWidgets import QApplication

from tracker.detectors.detectors import MESH_FACE_POINTS_COUNT
from tracker.detectors.manager import DetectorsManager
from tracker.detectors.mediapipe_detector import right_pupil
from tracker.gaze.averaged_origin_direction import AveragedEyeOriginDirection
from tracker.ui.calibration_window import CalibrationWindow
from tracker.utils.coordinates import Point, distance, \
    find_cross_point
from tracker.utils.fps import FPSLimiter
from tracker.utils.shared_objects import SharedVector, SharedFlag, SharedPoint

sys.path.append('../..')


def start_calibration(target_coordinates: SharedPoint, target_clicked: SharedFlag):
    app = QApplication(sys.argv)
    window = CalibrationWindow(target_coordinates, target_clicked)
    window.show()
    sys.exit(app.exec())


class GazePredictor:
    def __init__(self, target_sight_accepted: SharedFlag, gaze_coordinates: SharedPoint, detectors_manager: DetectorsManager):
        self.target_coordinates = SharedPoint('i', 0)
        self.target_sight_accepted = target_sight_accepted
        self.gaze_coordinates = gaze_coordinates
        self.detectors = detectors_manager

        self.gaze_origin = SharedVector('f', -1)
        self.gaze_direction = SharedVector('f', -1)

        self.samples_per_screen_corner: int = 2
        self.samples_for_averaging_positions: int = 5

        self.calibration_window = Process(target=start_calibration,
                                          args=(self.target_coordinates, self.target_sight_accepted),
                                          daemon=True)
        self.calibration_process = Process(target=self.calibrate, daemon=True)
        available = QApplication.screens()[-1].availableGeometry()
        self.screen_width = available.width()
        self.screen_height = available.height()

        self.calibration_process.start()
        self.calibration_window.start()

    def calibrate(self):
        best_right_center = np.load('best_right_pupil.pickle_994_normal.npy')
        best_right_center_2 = np.load('best_right_pupil_848_900k_large.npy')

        fps = FPSLimiter(240)

        left_top = Point(0, 0)
        right_top = Point(self.screen_width // 2, 0)
        right_bottom = Point(self.screen_width // 2, self.screen_height)
        left_bottom = Point(0, self.screen_height)

        screen_corners: list[Point] = [left_top, right_top, right_bottom, left_bottom]
        screen_corners_points: list[np.ndarray] = []


        for corner in screen_corners:
            self.target_coordinates.array[:] = corner.x, corner.y
            crossing_rays: list[tuple[np.ndarray, np.ndarray]] = []
            for _ in range(self.samples_per_screen_corner):
                while not self.target_sight_accepted:
                    if not fps.able_to_execute():
                        fps.throttle()
                    continue
                self.target_sight_accepted.set(False)

                right_eye = AveragedEyeOriginDirection(self.samples_per_screen_corner)
                for _ in range(self.samples_for_averaging_positions):
                    all_mesh_points = np.array(
                        [[p.x, p.y, p.z] for p in self.detectors.mesh.mesh])
                    mesh_points = all_mesh_points[:MESH_FACE_POINTS_COUNT]

                    right_origin_1 = np.sum(mesh_points[:MESH_FACE_POINTS_COUNT] *
                                     best_right_center[:, np.newaxis], axis=0) / np.sum(best_right_center)
                    right_origin_2 = np.sum(mesh_points[:MESH_FACE_POINTS_COUNT] *
                                     best_right_center_2[:, np.newaxis], axis=0) / np.sum(best_right_center_2)
                    right_origin = (right_origin_1 * 1.12 + right_origin_2) / 2.12
                    right_eye.origin.add_if_diff_from_avg(right_origin)
                    r_pupil = all_mesh_points[right_pupil]
                    right_direction = (r_pupil - right_origin) / distance(r_pupil, right_origin)
                    right_eye.direction.add_if_diff_from_avg(right_direction)
                    time.sleep(0.0125)
                crossing_rays.append((right_eye.origin.get(), right_eye.direction.get()))
            screen_corner_crossed_point = find_cross_point(crossing_rays).x
            screen_corners_points.append(screen_corner_crossed_point)

        print(screen_corners_points)

        #     eye_left_top, eye_right_bottom = Point(*self.eye_coordinates[:2]), Point(*self.eye_coordinates[2:])
        #     eye_center = calc_center(eye_left_top, eye_right_bottom)
        #     # eye_width_height = eye_right_bottom - eye_left_top
        #     normalized_pupil = ((eye_center - Point(*self.pupil_coordinates[:])))  # / eye_width_height) * 25
        #     pupil_coords.append(normalized_pupil)
        #
        # pupil_to_gaze = get_translation_maxtix(pupil_coords, screen_corners)
        #
        # while True:
        #     if not fps.able_to_execute():
        #         fps.throttle()
        #     eye_left_top, eye_right_bottom = Point(*self.eye_coordinates[:2]), Point(*self.eye_coordinates[2:])
        #     eye_center = calc_center(eye_left_top, eye_right_bottom)
        #     # eye_width_height = eye_right_bottom - eye_left_top
        #     normalized_pupil = ((eye_center - Point(*self.pupil_coordinates[:])) )  #/ eye_width_height) * 25
        #     predicted = translate_coordinates(pupil_to_gaze, normalized_pupil)
        #     self.gaze_coordinates.x = predicted.x
        #     self.gaze_coordinates.y = predicted.y
        #
        #     self.target_coordinates.x = self.gaze_coordinates[0]
        #     self.target_coordinates.y = self.gaze_coordinates[1]
        #
        #
        # # TODO: фактическое разрешение учитывать

