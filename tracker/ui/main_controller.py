from multiprocessing import Array

import cv2
import numpy
from PyQt6.QtCore import QObject, QTimerEvent, pyqtSlot
from PyQt6.QtWidgets import QMessageBox, QApplication

from tracker.abstractions import ID, DrawnObject
from tracker.camera_streamer import create_camera_streamer
from tracker.detectors.eye_detectors import HaarHoughEyeDetector
from tracker.detectors.pupil_detectors import DarkAreaPupilDetector
from tracker.detectors.managers import DetectorManager
from tracker.detectors.selector import EyeSelector
from tracker.gaze.gaze_predictor import GazePredictor
from tracker.gaze.gaze_video_server import GazeVideoServer
from tracker.object_tracker import TrackerWrapper
from tracker.protocol import BoundingBox
from tracker.ui.main_window import MainWindow
from tracker.utils.fps import FPSCounter, FPSLimiter, FPS_50, MSEC_IN_SEC


class MainController(QObject):

    def __init__(self, parent: MainWindow, id_camera: int = 0, fps=120, resolution=640):
        super().__init__(parent)
        self.video_stream_process, self.video_adapter =\
            create_camera_streamer(id_camera, fps, resolution)

        self.video_adapter.setup_video_frame()

        self.trackers: dict[ID, TrackerWrapper] = {}
        self.drawable_objects: dict[str, DrawnObject] = {}
        self.eye_box = Array('i', [0]*4)

        self.detector_manager: DetectorManager = None
        self.gaze_coordinates = Array('i', [0]*2)
        self.gaze_server: GazeVideoServer = None # GazeVideoServer(self.gaze_coordinates, self.video_adapter)
        self.gaze_predictor: GazePredictor = None # GazePredictor(self.gaze_coordinates, self.

        #self.calibrator_backend = GazePredictorBackend()
        self.window = parent

        self.fps = FPSCounter(2)
        self.throttle = FPSLimiter(40)
        self.refresh_timer = self.startTimer(int(FPS_50 * MSEC_IN_SEC))

        self.free_tracker_id: ID = ID(0)
        self.on_eye_select_requested()

    def timerEvent(self, a0: QTimerEvent):
        if not self.throttle.able_to_execute():
            self.throttle.throttle()
            # TODO: get coordinates
        coords = [BoundingBox(*t.coordinates_memory[:]) for t in self.trackers.values()]
        frame = numpy.copy(self.video_adapter.get_video_frame())
        for c in coords:
            frame = cv2.rectangle(frame, (int(c.x1), int(c.y1)), (int(c.x2), int(c.y2)), color=(255, 0, 0),
                                  thickness=2)

        if self.detector_manager:
            eye, pupil = self.detector_manager.detect()
            if pupil:
                cv2.circle(frame, (*pupil,), 2, (0, 255, 0), -1)
            if eye:
                cv2.rectangle(frame, (eye.x1, eye.y1), (eye.x2, eye.y2),
                          (255, 0, 0), 2)


        for object in self.drawable_objects.values():
            object.draw_on_frame(frame)

        self.window.update_video_frame(frame)

        if self.fps.able_to_calculate():
            self.fps.calculate()
            #print(f'frontend fps: {self.fps.calculate()}')
        self.fps.count_frame()

    def bind_selector_to_events(self, selector: EyeSelector):
        label = self.window.video_label
        label.on_mouse_click = selector.left_button_click
        label.on_mouse_move = selector.left_button_down_moved
        #label.on_mouse_release = selector.left_button_up
        label.on_mouse_release = selector.finish_selecting
        #label.on_enter_press = selector.finish_selecting

    def unbind_selector_from_events(self):
        label = self.window.video_label
        label.on_mouse_click = label.on_mouse_move = label.on_mouse_release = label.on_enter_press = None

    @pyqtSlot()
    def on_eye_select_requested(self):
        selector = EyeSelector('eye_selector', self.unbind_selector_from_events, self.on_selection_finished)
        self.bind_selector_to_events(selector)
        selector.start()
        self.drawable_objects[selector.name] = selector

    @pyqtSlot(int)
    def on_rotate(self, degree: int):
        self.video_adapter.rotate_degree.value = degree

    def on_selection_finished(self, selector: EyeSelector):
        self.eye_box[0] = selector.left_top.x
        self.eye_box[1] = selector.left_top.y
        self.eye_box[2] = selector.right_bottom.x
        self.eye_box[3] = selector.right_bottom.y
        if not self.detector_manager:
            self.on_detection_start(self.eye_box)
        #del self.drawable_objects[selector.name]

    def on_detection_start(self, eye_box: Array):
        box = BoundingBox(*self.eye_box[:])
        haar_detector = HaarHoughEyeDetector(eye_box, self.video_adapter, 90)
        dark_area_detector = DarkAreaPupilDetector(haar_detector.eye_coordinates, self.video_adapter, 180)
        self.detector_manager = DetectorManager(box,
                                                eye_detectors={0: haar_detector},
                                                pupil_detectors={0: dark_area_detector}
                                                )


    @pyqtSlot(BoundingBox)
    def on_new_tracker_requested(self, coords: BoundingBox):
        self.free_tracker_id += 1
        tracker = TrackerWrapper(self.free_tracker_id, coords, self.video_adapter)
        self.trackers[self.free_tracker_id] = tracker

    @pyqtSlot()
    def on_calibration_started(self):
        if len(QApplication.screens()) < 1:
            QMessageBox.warning(None, 'Ошибка', 'Необходимо подключить второй экран')
            return
        if not self.detector_manager:
            QMessageBox.warning(None, 'Ошибка', 'Необходимо выделить приблизительную область нахождения глаза')
            return
        self.gaze_predictor = GazePredictor(self.gaze_coordinates,
                                            self.detector_manager.eye_coordinates,
                                            self.detector_manager.pupil_coordinates)

    @pyqtSlot()
    def on_calibration_stopped(self):
        if self.gaze_predictor:
            try:
                self.gaze_predictor.calibration_process.kill()
            except:
                ...
            try:
                self.gaze_predictor.calibration_window.kill()
            except:
                ...
