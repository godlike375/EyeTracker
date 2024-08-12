import sys
from multiprocessing import Process

from PyQt6.QtWidgets import QApplication

from tracker.detectors.manager import DetectorsManager
from tracker.ui.calibration_window import CalibrationWindow
from tracker.utils.coordinates import Point, calc_center, get_translation_maxtix, translate_coordinates
from tracker.utils.fps import FPSLimiter
from tracker.utils.shared_objects import SharedVector, SharedFlag, SharedPoint

sys.path.append('../..')


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

        self.samples_per_screen_corner: int = 2

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
        fps = FPSLimiter(240)

        left_top = Point(0, 0)
        right_top = Point(self.screen_width, 0)
        right_bottom = Point(self.screen_width, self.screen_height)
        left_bottom = Point(0, self.screen_height)

        screen_corners: list[Point] = [left_top, right_top, right_bottom, left_bottom]

        eyes_gaze: list[list] = []


        for corner in screen_corners:
            self.target_coordinates.array[:] = corner.x, corner.y
            eyes_gaze.append([])
            for _ in range(self.samples_per_screen_corner):
                while not self.target_clicked:
                    if not fps.able_to_execute():
                        fps.throttle()
                    continue
                self.target_clicked.set(False)

                self.detectors.mesh.ca

            eye_left_top, eye_right_bottom = Point(*self.eye_coordinates[:2]), Point(*self.eye_coordinates[2:])
            eye_center = calc_center(eye_left_top, eye_right_bottom)
            # eye_width_height = eye_right_bottom - eye_left_top
            normalized_pupil = ((eye_center - Point(*self.pupil_coordinates[:])))  # / eye_width_height) * 25
            pupil_coords.append(normalized_pupil)

        pupil_to_gaze = get_translation_maxtix(pupil_coords, screen_corners)

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

