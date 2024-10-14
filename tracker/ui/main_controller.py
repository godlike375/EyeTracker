from multiprocessing import Array, Process

import cv2
import numpy
from PyQt6.QtCore import QObject, QTimerEvent, pyqtSlot
from PyQt6.QtWidgets import QMessageBox, QApplication

from tracker.abstractions import ID, DrawnObject
from tracker.camera import VideoAdapter
from tracker.detectors.mediapipe_detector import MediapipeMeshDetector
from tracker.detectors.manager import DetectorsManager
from tracker.detectors.selector import EyeSelector
from tracker.gaze.gaze_predictor import GazePredictor
from tracker.gaze.gaze_video_server import GazeVideoServer
from tracker.object_tracker import TrackerWrapper
from tracker.utils.coordinates import BoundingBox
from tracker.ui.main_window import MainWindow
from tracker.utils.fps import FPSCounter, MSEC_IN_SEC
from tracker.utils.shared_objects import SharedBox, SharedPoint, SharedFlag


class MainController(QObject):

    def __init__(self, parent: MainWindow, video_adapter: VideoAdapter, recording: SharedFlag, fps=120, ui_fps=25):
        super().__init__(parent)
        self.target_fps = fps
        self.video_adapter, self.recording = video_adapter, recording

        self.video_adapter.setup_video_frame()

        self.trackers: dict[ID, TrackerWrapper] = {}
        self.drawable_objects: dict[str, DrawnObject] = {}
        self.detect_area = SharedBox('i', -1)

        self.detector_manager: DetectorsManager = None
        self.processes: list[Process] = []

        self.on_screen_gaze_point = SharedPoint('i', 0)
        self.gaze_server: GazeVideoServer = None # GazeVideoServer(self.gaze_coordinates, self.video_adapter)
        self.gaze_predictor: GazePredictor = None # GazePredictor(self.gaze_coordinates, self.
        self.target_sight_accepted: SharedFlag = SharedFlag()

        self.window = parent

        self.fps = FPSCounter(2)
        self.refresh_timer = self.startTimer(int(1/ui_fps * MSEC_IN_SEC))

        self.free_tracker_id: ID = ID(0)
        self.on_eye_select_requested()

    def timerEvent(self, a0: QTimerEvent):
        # TODO: т.к. для сглаживания шумов нужны задержки,
        #  возможно стоит брать половину от средней задержки (количество кадров)
        #  и выводить просто кадры с опозданием, тогда будет слаженная информация на кадре
        coords = [BoundingBox(*t.coordinates_memory[:]) for t in self.trackers.values()]
        frame = numpy.copy(self.video_adapter.get_video_frame())
        for c in coords:
            frame = cv2.rectangle(frame, (int(c.x1), int(c.y1)), (int(c.x2), int(c.y2)), color=(255, 0, 0),
                                  thickness=2)

        if self.detector_manager:
            eyes, pupils = self.detector_manager.detect()
            for eye in eyes:
                if eye.is_valid:
                    cv2.rectangle(frame, (eye.x1, eye.y1), (eye.x2, eye.y2),
                          (255, 125, 0), 1)
            for pupil in pupils:
                if pupil.is_valid:
                    cv2.circle(frame, (pupil.x, pupil.y), 1, (0, 255, 0), -1)



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
        self.detect_area.left_top.array[:] = selector.left_top.x, selector.left_top.y
        self.detect_area.right_bottom.array[:] = selector.right_bottom.x, selector.right_bottom.y
        if not self.detector_manager:
            self.on_detection_start(self.detect_area)
        #del self.drawable_objects[selector.name]

    def on_detection_start(self, detect_area: SharedBox):
        #haar_eyes_detector = HaarEyeValidator(eye_box, self.video_adapter, self.target_fps * 2)
        #self.processes.append(haar_eyes_detector.start_process())
        # left_pupil_detector = DarkAreaPupilDetector(haar_eyes_detector.left_eye,
        #                                            self.video_adapter, self.target_fps * 2)
        # self.processes.append(left_pupil_detector.start_process())
        # right_pupil_detector = DarkAreaPupilDetector(haar_eyes_detector.right_eye,
        #                                             self.video_adapter, self.target_fps * 2)
        # self.processes.append(right_pupil_detector.start_process())
        # pupils_detector = BothPupilDetector(left_pupil_detector, right_pupil_detector)
        # TODO: pupil detectorы должны получать позицию глаз от менеджера, а не от одного детектора, обратная связь
        #  возможно надо вместо менеджера сделать точный и четкий конвейер просто
        face_mesh_detector = MediapipeMeshDetector(detect_area, self.video_adapter, self.target_fps * 2)
        self.processes.append(face_mesh_detector.start_process())
        self.detector_manager = DetectorsManager(detect_area, self.target_fps, face_mesh_detector) #, haar_eyes_detector)
        self.processes.append(self.detector_manager.start_process())


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
        self.gaze_predictor = GazePredictor(self.target_sight_accepted, self.on_screen_gaze_point, self.detector_manager)

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


    @pyqtSlot()
    def on_recording_started(self):
        self.recording.value = True

    @pyqtSlot()
    def on_recording_stopped(self):
        self.recording.value = False