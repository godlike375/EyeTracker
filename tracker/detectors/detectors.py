import time
from abc import abstractmethod
from multiprocessing import Array, Process
from multiprocessing.shared_memory import SharedMemory

import cv2
import numpy
import numpy as np

from tracker.abstractions import ProcessBased
from tracker.object_tracker import FPS_120
from tracker.utils.fps import FPSCounter, FPSLimiter


class PupilDetector(ProcessBased):
    def __init__(self, eye_box: Array, frame_memory: SharedMemory):
        super().__init__()
        self.coordinates = Array('i', [0] * 2)
        self.current_frame = frame_memory
        self.eye_box = eye_box

    @abstractmethod
    def mainloop(self):
        ...


class DarkAreaPupilDetector(PupilDetector):
    def __init__(self, eye_box: Array, frame_memory: SharedMemory):
        super().__init__(eye_box, frame_memory)
        self.process = Process(target=self.mainloop)
        self.process.start()

    def find_optimal_threshold(self, blurred):
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(blurred)
        # the more is min_val - the less is the multiplicator
        # best yet params: base_factor = -min_val / 254 + 1.465
        base_factor = -min_val / 257 + 1.4635
        base_factor = base_factor if base_factor > 1.004 else 1.004
        try_threshold = int((max(min_val, 1)) * base_factor)
        return try_threshold

    def preprocess_image(self, eye_frame: numpy.ndarray):
        gray = cv2.cvtColor(eye_frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        threshold = self.find_optimal_threshold(blurred)

        ret, eye_thresholded = cv2.threshold(blurred, threshold, 255, cv2.THRESH_BINARY_INV)
        kernel = np.ones((3, 3), np.uint8)
        eye_thresholded = cv2.dilate(eye_thresholded, kernel, iterations=1)
        return eye_thresholded

    def pupil_by_contours(self, eye_thresholded, ex, ey):
        pupil = None
        eye_contours, _ = cv2.findContours(eye_thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        largest_area = 25
        px, py, pw, ph = None, None, None, None
        for contour in eye_contours:
            M = cv2.moments(contour)
            area = M['m00']
            if area > largest_area:
                px, py, pw, ph = cv2.boundingRect(contour)
                cx = int(M["m10"] / area)
                cy = int(M["m01"] / area)
                largest_area = area
                pupil = (cx + ex, cy + ey)

        return pupil, px, py, pw, ph

    def pupil_by_circles(self, eye_thresholded, px, py, pw, ph, ex, ey):
        pupil_center = None
        pupil_frame = eye_thresholded[py:py + ph, px:px + pw]
        circles = cv2.HoughCircles(pupil_frame, cv2.HOUGH_GRADIENT, 1.27, 8,
                                   param1=23, param2=12, minRadius=7, maxRadius=570)
        max_radius = 0
        # Если обнаружены окружности
        if circles is not None:
            # Обход по обнаруженным окружностям
            for i in circles[0, :]:
                # Извлечение координат центра и радиуса
                center = (int(i[0]) + px + ex, int(i[1] + py + ey))
                radius = int(i[2])
                if radius > max_radius:
                    pupil_center = center
        return pupil_center

    def mainloop(self):
        raw = numpy.ndarray((480, 640, 3), dtype=numpy.uint8, buffer=self.current_frame.buf)
        fps = FPSLimiter(120)
        while True:
            if not fps.able_to_execute():
                time.sleep(FPS_120)
                continue
            ex, ey = self.eye_box[0], self.eye_box[1]
            eye_frame = raw[self.eye_box[1]: self.eye_box[3], self.eye_box[0]: self.eye_box[2]]
            # TODO: add cv2.erosion and decrease GausianBlur ! May be better results
            eye_thresholded = self.preprocess_image(eye_frame)

            cv2.imshow('thresh', eye_thresholded)
            cv2.waitKey(1)

            pupil_by_contours, px, py, pw, ph = self.pupil_by_contours(eye_thresholded, ex, ey)

            pupil_by_circles = None
            if pupil_by_contours is not None:
                pupil_by_circles = self.pupil_by_circles(eye_thresholded, px, py, pw, ph, ex, ey)

            if pupil_by_circles is not None:
                self.coordinates[0], self.coordinates[1] = \
                    (pupil_by_circles[0] + pupil_by_contours[0]) // 2, (pupil_by_circles[1] + pupil_by_contours[1]) // 2
            else:
                self.coordinates[0], self.coordinates[1] = pupil_by_contours


