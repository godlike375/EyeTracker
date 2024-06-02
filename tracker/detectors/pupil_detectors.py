import time
from abc import abstractmethod
from multiprocessing import Array, Process
from multiprocessing.shared_memory import SharedMemory

import cv2
import numpy
import numpy as np

from tracker.abstractions import ProcessBased
from tracker.detectors.jonnedtc import GradientIntersect
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

    def remove_zeroes_and_take_percentile(self, hist, percent):
        pairs = [(i, int(hist[i][0])) for i in range(len(hist))]
        pairs.sort(key=lambda x: x[1])
        pairs = [(i, v) for (i, v) in pairs if v > 0]
        percentile_25th = int(len(pairs) * percent / 100)
        return pairs[percentile_25th:]

    def find_optimal_threshold(self, blurred, base_factor=None):
        kernel = np.ones((2, 2), np.uint8)
        blurred = cv2.dilate(blurred, kernel, iterations=1)
        hist = cv2.calcHist([blurred], [0], None, [256], [0, 256])
        # the coefficients are optimal in most scenarios
        sorted_by_values = self.remove_zeroes_and_take_percentile(hist, percent=1.0325)
        sorted_by_indexes = sorted(sorted_by_values, key=lambda x: x[0])
        min_val = max(sorted_by_indexes[0][0], 1)
        max_val = sorted_by_indexes[-1][0]
        base_factor = base_factor or ((max_val - min_val) / 255) ** 2.4685 + 1
        # TODO: если широкий диапазон - использовать контуры больше. Если узкий - круги
        base_factor = max(base_factor, 1)
        try_threshold = int(min_val * base_factor)
        return try_threshold

    def preprocess_image(self, raw: numpy.ndarray):
        eye_frame = raw[self.eye_box[1]: self.eye_box[3], self.eye_box[0]: self.eye_box[2]]
        gray = cv2.cvtColor(eye_frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (9, 9), 0)
        return blurred


class DarkAreaPupilDetector(PupilDetector):
    def __init__(self, eye_box: Array, frame_memory: SharedMemory, resolution: tuple[int, int]):
        super().__init__(eye_box, frame_memory, resolution)
        self.process = Process(target=self.mainloop)
        self.process.start()

    def find_threshold_and_detect(self, blurred: numpy.ndarray, ex, ey):
        kernel = np.ones((3, 3), np.uint8)
        blurred = cv2.dilate(blurred, kernel, iterations=1)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(blurred)
        min_val = max(min_val, 1)
        # Вычислите средний динамический диапазон яркости

        hist = [int(h[0]) for h in hist]
        peak_index = 0
        for i, (prev, next) in enumerate(zip(hist[:-2], hist[1:])):
            if prev > next + 1:
                peak_index = i
                break
        peak_value = hist[peak_index]
        threshold = int((min_val + peak_value) / 1.25)
        print(threshold)
        thresholded_img = cv2.threshold(blurred, threshold, 255, cv2.THRESH_BINARY_INV)[1]

        pupil, px, py, pw, ph, largest_area = self.pupil_by_contours(thresholded_img, ex, ey)

        # step = 1.3385
        # prev_area = 1
        # max_steps = 14.875
        # threshold = step + peak_value * 1.06325
        # while True:
        #     thresholded_img = cv2.threshold(blurred, threshold, 255, cv2.THRESH_BINARY_INV)[1]
        #
        #     pupil, px, py, pw, ph, largest_area = self.pupil_by_contours(thresholded_img, ex, ey)
        #     if largest_area <= prev_area:
        #         max_steps -= 2.215
        #     if max_steps <= 0.35 or (prev_area / largest_area <= 0.714 and largest_area - prev_area >= 31):
        #         break
        #     threshold += step

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
            threshold = self.find_optimal_threshold(blurred)
            thresholded_img = cv2.threshold(blurred, threshold, 255, cv2.THRESH_BINARY_INV)[1]
            pupil_by_contours, px, py, pw, ph, area = self.pupil_by_contours(thresholded_img, ex, ey)
            cv2.imshow('threshold', thresholded_img)
            cv2.waitKey(1)

            pupil_by_circles = None
            if pupil_by_contours is not None:
            #     pupil_by_circles = self.pupil_by_circles(blurred, px, py, pw, ph, ex, ey)
            #
            # if pupil_by_circles is not None:
            #     self.coordinates[0], self.coordinates[1] = \
            #         (pupil_by_circles[0] + pupil_by_contours[0]) // 2,\
            #         (pupil_by_circles[1] + pupil_by_contours[1]) // 2
            # elif pupil_by_contours:
                self.coordinates[0], self.coordinates[1] = pupil_by_contours


class PupilLibraryDetector(PupilDetector):
    def __init__(self, eye_box: Array, frame_memory: SharedMemory, resolution: tuple[int, int]):
        super().__init__(eye_box, frame_memory, resolution)
        self.process = Process(target=self.mainloop)
        self.process.start()

    def mainloop(self):
        raw = numpy.ndarray((*self.resolution, 3), dtype=numpy.uint8, buffer=self.current_frame.buf)
        detector = GradientIntersect()
        fps = FPSLimiter(120)

        eye_frame = raw[self.eye_box[1]: self.eye_box[3], self.eye_box[0]: self.eye_box[2]]
        gray = cv2.cvtColor(eye_frame, cv2.COLOR_BGR2GRAY)
        ex, ey = self.eye_box[0], self.eye_box[1]
        result = detector.locate(gray)
        self.coordinates[0], self.coordinates[1] = int(result[1] + ex), int(result[0] + ey)

        while True:
            if not fps.able_to_execute():
                time.sleep(FPS_120)
                continue
            eye_frame = raw[self.eye_box[1]: self.eye_box[3], self.eye_box[0]: self.eye_box[2]]
            gray = cv2.cvtColor(eye_frame, cv2.COLOR_BGR2GRAY)
            ex, ey = self.eye_box[0], self.eye_box[1]
            result = detector.track(gray, result)
            self.coordinates[0], self.coordinates[1] = int(result[1] + ex), int(result[0] + ey)