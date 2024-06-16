import sys
from multiprocessing import Process, Array, Value

import numpy
from PyQt6.QtWidgets import QApplication
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsRegressor

from tracker.ui.calibration_window import CalibrationWindow
from tracker.utils.coordinates import Point, calc_center
from tracker.utils.fps import FPSLimiter

sys.path.append('../..')


def start_calibration(target_coordinates: Array, target_clicked: Value):
    app = QApplication(sys.argv)
    window = CalibrationWindow(target_coordinates, target_clicked)
    window.show()
    sys.exit(app.exec())


class GazePredictor:
    def __init__(self, gaze_coordinates: Array, eye_coordinates: Array, pupil_coordinates: Array):
        self.target_coordinates = Array('i', [0]*2)
        self.target_clicked = Value('b', False)
        self.gaze_coordinates = gaze_coordinates
        self.eye_coordinates = eye_coordinates
        self.pupil_coordinates = pupil_coordinates
        self.calibration_window = Process(target=start_calibration,
                                          args=(self.target_coordinates, self.target_clicked),
                                          daemon=True)
        self.calibration_process = Process(target=self.calibrate, daemon=True)
        available = QApplication.screens()[-1].availableGeometry()
        self.parts = 6
        self.step_x = available.width() // self.parts
        self.step_y = available.height() // self.parts

        self.calibration_process.start()
        self.calibration_window.start()

    def calibrate(self):
        fps = FPSLimiter(120)
        eye = numpy.empty(shape=(0, 4), dtype=int)
        pupil = numpy.empty(shape=(0, 2), dtype=int)
        gaze_x = numpy.empty(shape=(0,), dtype=int)
        gaze_y = numpy.empty(shape=(0,), dtype=int)
        for i in range(self.parts):
            self.target_coordinates[1] = self.step_y * i
            for j in range(self.parts):
                self.target_coordinates[0] = self.step_x * j
                while not self.target_clicked.value:
                    if not fps.able_to_execute():
                        fps.throttle()
                    continue
                eye_left_top, eye_right_bottom = Point(*self.eye_coordinates[:2]), Point(*self.eye_coordinates[2:])
                eye_center = calc_center(eye_left_top, eye_right_bottom)
                eye_width_height = eye_right_bottom - eye_left_top
                normalized_pupil = ((eye_center - Point(*self.pupil_coordinates[:])) )#/ eye_width_height) * 25
                pupil = numpy.append(pupil, numpy.array([[*normalized_pupil]]), axis=0)

                eye = numpy.append(eye, numpy.array([self.eye_coordinates[:]]), axis=0)
                gaze_x = numpy.append(gaze_x, numpy.array([self.target_coordinates[0]+35]), axis=0)
                gaze_y = numpy.append(gaze_y, numpy.array([self.target_coordinates[1]+7]), axis=0)
                self.target_clicked.value = False

        train_pupil, test_pupil, train_gaze_x, test_gaze_x = train_test_split(pupil, gaze_x, test_size=0.125)
        train_pupil2, test_pupil2, train_gaze_y, test_gaze_y = train_test_split(pupil, gaze_y, test_size=0.125)
        rfx = KNeighborsRegressor(n_neighbors=9)
        rfx.fit(train_pupil, train_gaze_x)
        rf_pred = rfx.predict(test_pupil)
        res = numpy.sqrt(mean_squared_error(test_gaze_x, rf_pred))
        print(f'X error = {res}, predicted = {rf_pred}, actual = {test_gaze_x}')

        rfy = KNeighborsRegressor(n_neighbors=9)
        rfy.fit(train_pupil2, train_gaze_y)
        rf_pred = rfy.predict(test_pupil2)
        res = numpy.sqrt(mean_squared_error(test_gaze_y, rf_pred))
        print(f'Y error = {res}, predicted = {rf_pred}, actual = {test_gaze_y}')

        while True:
            if not fps.able_to_execute():
                fps.throttle()
            eye_left_top, eye_right_bottom = Point(*self.eye_coordinates[:2]), Point(*self.eye_coordinates[2:])
            eye_center = calc_center(eye_left_top, eye_right_bottom)
            eye_width_height = eye_right_bottom - eye_left_top
            normalized_pupil = ((eye_center - Point(*self.pupil_coordinates[:])) )#/ eye_width_height) * 25
            pupil = numpy.array([[*normalized_pupil]])
            self.gaze_coordinates[0] = rfx.predict(pupil).astype(numpy.int64)[0]
            self.gaze_coordinates[1] = rfy.predict(pupil).astype(numpy.int64)[0]
            self.target_clicked.value = False
            self.target_coordinates[0] = self.gaze_coordinates[0]
            self.target_coordinates[1] = self.gaze_coordinates[1]


        # TODO: фактическое разрешение учитывать

