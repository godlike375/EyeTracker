import time
from abc import abstractmethod
from multiprocessing import Array, Process
from multiprocessing.shared_memory import SharedMemory

import cv2
import numpy
import numpy as np
from pupil_detectors import Detector2D

from tracker.abstractions import ProcessBased
from tracker.object_tracker import FPS_120
from tracker.utils.fps import FPSCounter, FPSLimiter


class PupilDetector(ProcessBased):
    def __init__(self, eye_box: Array, frame_memory: SharedMemory, resolution: tuple[int, int]):
        super().__init__()
        self.coordinates = Array('i', [0] * 2)
        self.current_frame = frame_memory
        self.eye_box = eye_box
        self.resolution = resolution

    @abstractmethod
    def mainloop(self):
        ...

    def find_optimal_threshold(self, blurred, base_factor=None):
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(blurred)
        # the more is min_val - the less is the multiplicator
        # best yet params: base_factor = -min_val / 254 + 1.465
        # TODO: improve to increse stability:
        #  чем больший диапазон освещения на участке фото, тем обычно проще найти зрачок.
        #  Значит при маленьком диапазоне нужно допуск меньше что-ли делать
        # base_factor = ((max_val - min_val) / 212) ** 2.785 + 0.75
        # base_factor = ((max_val - min_val) / 243) ** 2.67 + 0.685
        # base_factor = ((max_val - min_val) / 227) ** 2.77 + 0.71
        base_factor = base_factor or ((max_val - min_val) / 248) ** 4.64 + 1.0518
        #base_factor = 1.0515
        # TODO: если широкий диапазон - использовать контуры больше. Если узкий - круги
        base_factor = base_factor if base_factor > 1 else 1
        try_threshold = int((max(min_val, 1)) * base_factor)
        return try_threshold

    def preprocess_image(self, raw: numpy.ndarray):
        eye_frame = raw[self.eye_box[1]: self.eye_box[3], self.eye_box[0]: self.eye_box[2]]
        gray = cv2.cvtColor(eye_frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        return blurred


class DarkAreaPupilDetector(PupilDetector):
    def __init__(self, eye_box: Array, frame_memory: SharedMemory, resolution: tuple[int, int]):
        super().__init__(eye_box, frame_memory, resolution)
        self.process = Process(target=self.mainloop)
        self.process.start()

    def find_threshold_and_detect(self, blurred: numpy.ndarray, ex, ey):
        kernel = np.ones((2, 2), np.uint8)
        blurred = cv2.dilate(blurred, kernel, iterations=1)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(blurred)
        min_val = max(min_val, 1)

        step = 1.3385
        prev_area = 1
        max_steps = 14.875
        threshold = step + min_val * 1.06325
        while True:
            thresholded_img = cv2.threshold(blurred, threshold, 255, cv2.THRESH_BINARY_INV)[1]

            pupil, px, py, pw, ph, largest_area = self.pupil_by_contours(thresholded_img, ex, ey)
            if largest_area <= prev_area:
                max_steps -= 2.215
            if max_steps <= 0.35 or (prev_area / largest_area <= 0.714 and largest_area - prev_area >= 31):
                break
            threshold += step

            # Возвращаем найденный порог
        cv2.imshow('eye thresholded', thresholded_img)
        cv2.waitKey(1)
        return pupil, px, py, pw, ph, largest_area

    def pupil_by_contours(self, eye_thresholded, ex, ey):
        pupil = None
        eye_contours, _ = cv2.findContours(eye_thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        largest_area = 1
        px, py, pw, ph = None, None, None, None
        for contour in eye_contours:
            M = cv2.moments(contour)
            area = M['m00']
            if area >= largest_area:
                px, py, pw, ph = cv2.boundingRect(contour)
                cx = int(M["m10"] / area)
                cy = int(M["m01"] / area)
                largest_area = area
                pupil = (cx + ex, cy + ey)

        return pupil, px, py, pw, ph, largest_area

    def pupil_by_circles(self, eye_thresholded, px, py, pw, ph, ex, ey):
        pupil_center = None
        pupil_frame = eye_thresholded[py:py + ph, px:px + pw]
        circles = cv2.HoughCircles(pupil_frame, cv2.HOUGH_GRADIENT, 1.62, 9,
                                   param1=11, param2=8, minRadius=3, maxRadius=570)
        max_radius = 1
        # Если обнаружены окружности
        if circles is not None:
            # Обход по обнаруженным окружностям
            for i in circles[0, :]:
                # Извлечение координат центра и радиуса
                center = (int(i[0]) + px + ex, int(i[1] + py + ey))
                radius = int(i[2])
                if radius > max_radius:
                    pupil_center = center
                    eye_thresholded = cv2.circle(eye_thresholded, (int(i[0] + px), int(i[1] + py)), radius=2, color=(255,255,255), thickness=2)
        # cv2.imshow('circles', eye_thresholded)
        return pupil_center

    def mainloop(self):
        raw = numpy.ndarray((*self.resolution, 3), dtype=numpy.uint8, buffer=self.current_frame.buf)
        fps = FPSLimiter(240)
        while True:
            if not fps.able_to_execute():
                fps.throttle()
                continue
            ex, ey = self.eye_box[0], self.eye_box[1]
            blurred = self.preprocess_image(raw)
            pupil_by_contours, px, py, pw, ph, area = self.find_threshold_and_detect(blurred, ex, ey)

            pupil_by_circles = None
            if pupil_by_contours is not None:
                pupil_by_circles = self.pupil_by_circles(blurred, px, py, pw, ph, ex, ey)

            if pupil_by_circles is not None:
                self.coordinates[0], self.coordinates[1] = \
                    (pupil_by_circles[0] + pupil_by_contours[0]) // 2,\
                    (pupil_by_circles[1] + pupil_by_contours[1]) // 2
            elif pupil_by_contours:
                self.coordinates[0], self.coordinates[1] = pupil_by_contours


class PupilLibraryDetector(PupilDetector):
    def __init__(self, eye_box: Array, frame_memory: SharedMemory, resolution: tuple[int, int]):
        super().__init__(eye_box, frame_memory, resolution)
        self.process = Process(target=self.mainloop)
        self.process.start()

    def mainloop(self):
        raw = numpy.ndarray((*self.resolution, 3), dtype=numpy.uint8, buffer=self.current_frame.buf)
        detector = Detector2D()
        fps = FPSLimiter(120)
        while True:
            if not fps.able_to_execute():
                time.sleep(FPS_120)
                continue
            eye_frame = raw[self.eye_box[1]: self.eye_box[3], self.eye_box[0]: self.eye_box[2]]
            gray = cv2.cvtColor(eye_frame, cv2.COLOR_BGR2GRAY)
            ex, ey = self.eye_box[0], self.eye_box[1]
            result = detector.detect(gray)
            if result['confidence'] < 0.4:
                continue
            x, y = result['location']
            self.coordinates[0], self.coordinates[1] = int(x + ex), int(y + ey)