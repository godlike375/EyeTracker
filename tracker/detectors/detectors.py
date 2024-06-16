from abc import abstractmethod
from math import sqrt
from multiprocessing import Array, Process
from multiprocessing.shared_memory import SharedMemory
from statistics import mean
from time import sleep

import cv2
import numpy
import numpy as np

from tracker.abstractions import ProcessBased
from tracker.camera_streamer import VideoAdapter
from tracker.utils.fps import FPSLimiter


class Detector(ProcessBased):
    def __init__(self, eye_box: Array, video_adapter: VideoAdapter, target_fps: int):
        super().__init__()
        self.video_adapter = video_adapter
        self.eye_box = eye_box
        self.fps = FPSLimiter(target_fps)
        self.process = Process(target=self.mainloop, daemon=True)
        self.process.start()

    def mainloop(self):
        self.video_adapter.setup_video_frame()
        while True:
            if not self.fps.able_to_execute():
                self.fps.throttle()
            self.detect(self.video_adapter.get_video_frame())

    @abstractmethod
    def detect(self, raw: numpy.ndarray):
        ...

    def negative_half_square(self, a):
        if a<0:
            return -(a*a)*1.7125
        return a*a*1.7125

    def remove_zeroes_and_take_percentile(self, hist, percent):
        pairs = [(i, int(hist[i][0])) for i in range(len(hist))]
        pairs.sort(key=lambda x: x[1])
        pairs = [(i, v) for (i, v) in pairs if v > 0]


        base_threshold = 117
        weights = [int(self.negative_half_square(base_threshold - i) * (v ** 0.1194)) for (i, v) in pairs]
        weighted = [(pair, weight) for pair, weight in zip(pairs, weights) if weight > 0]
        weighted.sort(key=lambda x: x[1], reverse=True)

        percentile = int(len(weighted) * percent / 100)
        try:
            return max(weighted[:percentile], key=lambda x: x[0][0])[0][0]
        except:
            return base_threshold

    def find_optimal_threshold(self, blurred, base_factor=None):
        hist = cv2.calcHist([blurred], [0], None, [256], [0, 256])
        # the coefficients are optimal in most scenarios
        threshold = self.remove_zeroes_and_take_percentile(hist, percent=8.02)
        return threshold

    def get_eye_frame(self, raw: numpy.ndarray):
        while True:
            eye_frame = raw[self.eye_box[1]: self.eye_box[3], self.eye_box[0]: self.eye_box[2]]
            try:
                gray = cv2.cvtColor(eye_frame, cv2.COLOR_BGR2GRAY)
                return gray
            except:
                sleep(1/50)
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
    def __init__(self, eye_box: Array, video_adapter: VideoAdapter, target_fps: int):
        self.eye_coordinates = Array('i', [0] * 4)
        super().__init__(eye_box, video_adapter, target_fps)


class PupilDetector(Detector):
    def __init__(self, eye_box: Array, video_adapter: VideoAdapter, target_fps: int):
        self.pupil_coordinates = Array('i', [0] * 2)
        super().__init__(eye_box, video_adapter, target_fps)
