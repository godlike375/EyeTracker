from abc import abstractmethod
from multiprocessing import Array, Process
from multiprocessing.shared_memory import SharedMemory
from time import sleep

import cv2
import numpy
import numpy as np

from tracker.abstractions import ProcessBased
from tracker.utils.fps import FPSLimiter


class Detector(ProcessBased):
    def __init__(self, eye_box: Array, frame_memory: SharedMemory, resolution: tuple[int, int], target_fps: int):
        super().__init__()
        self.current_frame = frame_memory
        self.eye_box = eye_box
        self.resolution = resolution
        self.fps = FPSLimiter(target_fps)
        self.process = Process(target=self.mainloop)
        self.process.start()

    def numpy_array_from_shared_memory(self):
        return numpy.ndarray((*self.resolution, 3), dtype=numpy.uint8, buffer=self.current_frame.buf)

    def mainloop(self):
        raw = self.numpy_array_from_shared_memory()
        while True:
            if not self.fps.able_to_execute():
                self.fps.throttle()
            self.detect(raw)

    @abstractmethod
    def detect(self, raw: numpy.ndarray):
        ...

    def remove_zeroes_and_take_percentile(self, hist, percent):
        pairs = [(i, int(hist[i][0])) for i in range(len(hist))]
        pairs.sort(key=lambda x: x[1])
        pairs = [(i, v) for (i, v) in pairs if v > 0]
        percentile_25th = int(len(pairs) * percent / 100)
        return pairs[percentile_25th:]

    def find_optimal_threshold(self, blurred, base_factor=None):
        hist = cv2.calcHist([blurred], [0], None, [256], [0, 256])
        # the coefficients are optimal in most scenarios
        sorted_by_values = self.remove_zeroes_and_take_percentile(hist, percent=1.03)
        sorted_by_indexes = sorted(sorted_by_values, key=lambda x: x[0])
        min_val = max(sorted_by_indexes[0][0], 1)
        max_val = max(sorted_by_indexes[-1][0], 2)
        # the coefficients are optimal in most scenarios

        # base_factor = base_factor or ((max_val - min_val) ** 1.65 / 255 ** 1.65) + 0.6
        # base_factor = max(base_factor, 1.07)

        base_factor = base_factor or ((max_val - min_val) ** 1.18 / 255 ** 1.18) ** 1.1 + 0.71
        base_factor = max(base_factor, 1.078)

        # latest
        # base_factor = base_factor or ((max_val - min_val) ** 1.5 / 255 ** 1.5) + 0.45
        # base_factor = max(base_factor, 1.085)

        # base_factor = base_factor or ((max_val - min_val) / 255) ** 1.11 + 0.5
        # base_factor = max(base_factor, 1.038)
        # TODO: пересчитывать только если диапазон поменялся больше чем на N%
        try_threshold = int(min_val * base_factor)
        return try_threshold

    def get_eye_frame(self, raw: numpy.ndarray):
        while True:
            eye_frame = raw[self.eye_box[1]: self.eye_box[3], self.eye_box[0]: self.eye_box[2]]
            try:
                gray = cv2.cvtColor(eye_frame, cv2.COLOR_BGR2GRAY)
                return gray
            except:
                sleep(1/50)
                continue

    def blur_image(self, gray: numpy.ndarray, gaussian=0, dilate=0, erode=0):
        blurred = gray
        if gaussian:
            blurred = cv2.GaussianBlur(blurred, (gaussian, gaussian), 0)
        if dilate:
            kernel = np.ones((dilate, dilate), np.uint8)
            blurred = cv2.dilate(blurred, kernel, iterations=1)
        if erode:
            kernel = np.ones((erode, erode), np.uint8)
            blurred = cv2.erode(blurred, kernel, iterations=1)
        return blurred


class EyeDetector(Detector):
    def __init__(self, eye_box: Array, frame_memory: SharedMemory, resolution: tuple[int, int], target_fps: int):
        self.eye_coordinates = Array('i', [0] * 4)
        super().__init__(eye_box, frame_memory, resolution, target_fps)


class PupilDetector(Detector):
    def __init__(self, eye_box: Array, frame_memory: SharedMemory, resolution: tuple[int, int], target_fps: int):
        self.pupil_coordinates = Array('i', [0] * 2)
        super().__init__(eye_box, frame_memory, resolution, target_fps)
