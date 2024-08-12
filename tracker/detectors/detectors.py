from abc import abstractmethod
from multiprocessing import Process
from time import sleep

import cv2
import numpy
import numpy as np

from tracker.abstractions import ProcessBased
from tracker.camera import VideoAdapter
from tracker.utils.fps import FPSLimiter, FPS_120
from tracker.utils.shared_objects import SharedBox, SharedPoint, SharedVector, INVALID_VALUE


MESH_POINTS_COUNT = 478


class Detector(ProcessBased):
    def __init__(self, detect_area: SharedBox, video_adapter: VideoAdapter, target_fps: int):
        super().__init__()
        self.video_adapter = video_adapter.send_to_process()
        self._detect_area = detect_area
        self.fps = FPSLimiter(target_fps)

    def start_process(self):
        process = Process(target=self.mainloop, daemon=True)
        process.start()
        return process

    @abstractmethod
    def detect(self, raw: numpy.ndarray):
        ...

    def can_detect_eyes(self) -> bool:
        return False

    def can_detect_pupil(self) -> bool:
        return False

    def can_detect_pupils(self) -> bool:
        return False

    def can_detect_mesh(self) -> bool:
        return False

    @abstractmethod
    def detect_eyes(self) -> tuple[SharedBox, SharedBox]:...

    @abstractmethod
    def detect_pupil(self) -> SharedPoint:...

    @abstractmethod
    def detect_pupils(self) -> tuple[SharedPoint, SharedPoint]:...

    @abstractmethod
    def detect_mesh(self) -> list[SharedVector]:...

    def mainloop(self):
        self.video_adapter.setup_video_frame()
        while True:
            if not self.fps.able_to_execute():
                self.fps.throttle()
            self.detect(self.video_adapter.get_video_frame())

    def get_eye_rgb_frame(self, raw: numpy.ndarray):
        return raw[self._detect_area.y1: self._detect_area.y2, self._detect_area.x1: self._detect_area.x2]

    def get_eye_frame(self, raw: numpy.ndarray):
        while True:
            eye_frame = self.get_eye_rgb_frame(raw)
            try:
                gray = cv2.cvtColor(eye_frame, cv2.COLOR_BGR2GRAY)
                return gray
            except:
                sleep(FPS_120)
                continue

    def blur_image(self, gray: numpy.ndarray, blur=0, dilate=0, erode=0):
        blurred = gray
        if blur:
            blurred = cv2.medianBlur(blurred, blur)
        if dilate:
            kernel = np.ones((dilate, dilate), np.uint8)
            blurred = cv2.dilate(blurred, kernel, iterations=1)
        if erode:
            kernel = np.ones((erode, erode), np.uint8)
            blurred = cv2.erode(blurred, kernel, iterations=1)
        return blurred

    def contrast_image(self, frame: numpy.ndarray, contrast=1.3, brightness = -60):
        return cv2.addWeighted(frame, contrast, numpy.zeros(frame.shape, frame.dtype), 0, brightness)


class EyeDetector(Detector):
    def __init__(self, *args, **kwargs):
        self.left_eye = SharedBox('i', INVALID_VALUE)
        self.right_eye = SharedBox('i', INVALID_VALUE)
        super().__init__(*args, **kwargs)


    def can_detect_eyes(self) -> bool: return True

    def detect_eyes(self) -> tuple[SharedBox, SharedBox]: return self.left_eye, self.right_eye

class PupilDetector(Detector):
    def __init__(self, *args, **kwargs):
        self.pupil = SharedPoint('i', -1)
        super().__init__(*args, **kwargs)

    def can_detect_pupil(self): return True

    def detect_pupil(self) -> SharedPoint: return self.pupil


class BothPupilDetector(Detector):
    def __init__(self, left_detector: PupilDetector, right_detector: PupilDetector):
        self.left = left_detector
        self.right = right_detector

    def can_detect_pupils(self): return True

    def detect_pupils(self) -> tuple[SharedPoint, SharedPoint]: return self.left.pupil, self.right.pupil


class FaceMeshDetector(BothPupilDetector, EyeDetector):
    def __init__(self, *args, **kwargs):
        self.mesh: list[SharedVector] = [SharedVector('f', -1) for _ in range(MESH_POINTS_COUNT)]
        self.left_pupil = SharedPoint('i', INVALID_VALUE)
        self.right_pupil = SharedPoint('i', INVALID_VALUE)
        EyeDetector.__init__(self, *args, **kwargs)

    def can_detect_mesh(self) -> bool: return True

    def detect_mesh(self) -> list[SharedVector]: return self.mesh