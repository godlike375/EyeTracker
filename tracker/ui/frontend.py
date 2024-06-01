from functools import partial
from multiprocessing import Array

import cv2
import numpy
from PyQt6.QtCore import QObject, QTimerEvent, pyqtSlot

from tracker.abstractions import ID, DrawnObject, ProcessBased
from tracker.camera_streamer import create_camera_streamer
from tracker.detectors.pupil_detectors import DarkAreaPupilDetector, PupilLibraryDetector
from tracker.detectors.managers import PupilDetectorManager
from tracker.detectors.selector import EyeSelector
from tracker.object_tracker import TrackerWrapper
from tracker.protocol import BoundingBox
from tracker.ui.main_window import MainWindow
from tracker.utils.coordinates import Point
from tracker.utils.fps import FPSCounter, FPSLimiter
from tracker.utils.image_processing import get_resolution

FPS_50 = 1 / 50


class Frontend(QObject):

    def __init__(self, parent: MainWindow, id_camera: int = 0, fps=120, resolution=640):
        super().__init__(parent)
        self.video_frame, self.video_stream_process, self.frame_memory =\
            create_camera_streamer(id_camera, fps, resolution)

        self.trackers: dict[ID, TrackerWrapper] = {}
        self.drawable_objects: dict[str, DrawnObject] = {}
        self.eye_box = Array('i', [0]*4)

        self.pupil_manager: PupilDetectorManager = None

        #self.calibrator_backend = GazePredictorBackend()
        self.window = parent

        self.fps = FPSCounter(2)
        self.throttle = FPSLimiter(40)
        self.refresh_timer = self.startTimer(int(1 / 40 * 1000))

        self.free_tracker_id: ID = ID(0)

    def timerEvent(self, a0: QTimerEvent):
        if not self.throttle.able_to_execute():
            self.throttle.throttle()
            # TODO: get coordinates
        coords = [BoundingBox(*t.coordinates_memory[:]) for t in self.trackers.values()]
        frame = numpy.copy(self.video_frame)
        for c in coords:
            frame = cv2.rectangle(frame, (int(c.x1), int(c.y1)), (int(c.x2), int(c.y2)), color=(255, 0, 0),
                                  thickness=2)

        if self.pupil_manager:
            pupil: Point = self.pupil_manager.detect()
            cv2.circle(frame, (*pupil,), 3, (0, 255, 0), -1)

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
        label.on_mouse_release = selector.left_button_up
        label.on_enter_press = selector.finish_selecting

    def unbind_selector_from_events(self):
        label = self.window.video_label
        label.on_mouse_click = label.on_mouse_move = label.on_mouse_release = label.on_enter_press = None

    @pyqtSlot()
    def on_eye_select_requested(self):
        selector = EyeSelector('eye_selector', self.unbind_selector_from_events, self.on_selection_finished)
        self.bind_selector_to_events(selector)
        selector.start()
        self.drawable_objects[selector.name] = selector

    def on_selection_finished(self, selector: EyeSelector):
        self.eye_box[0] = selector.left_top.x
        self.eye_box[1] = selector.left_top.y
        self.eye_box[2] = selector.right_bottom.x
        self.eye_box[3] = selector.right_bottom.y
        self.on_pupil_detector_start(self.eye_box)
        del self.drawable_objects[selector.name]

    def on_pupil_detector_start(self, eye_box: Array):
        self.pupil_manager = PupilDetectorManager({0: DarkAreaPupilDetector(eye_box, self.frame_memory,
                                                   get_resolution(self.video_frame))})#,
                                                   #1: PupilLibraryDetector(eye_box, self.frame_memory,
                                                   #                         get_resolution(self.video_frame))})

    @pyqtSlot(BoundingBox)
    def on_new_tracker_requested(self, coords: BoundingBox):
        self.free_tracker_id += 1
        tracker = TrackerWrapper(self.free_tracker_id, coords, self.frame_memory)
        self.trackers[self.free_tracker_id] = tracker
