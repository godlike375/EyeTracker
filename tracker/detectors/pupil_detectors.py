import time
from multiprocessing import Array, Process
from multiprocessing.shared_memory import SharedMemory

import cv2
import numpy

from tracker.detectors.detectors import Detector, PupilDetector
from tracker.detectors.jonnedtc import IsophoteCurvature
from tracker.utils.denoise import MovingAverageDenoiser
from tracker.utils.coordinates import Point


class DarkAreaPupilDetector(PupilDetector):
    def mainloop(self):
        self.threshold = MovingAverageDenoiser(3)
        self.x = MovingAverageDenoiser(2)
        self.y = MovingAverageDenoiser(2)
        super().mainloop()

    def negative_half_square(self, a):
        if a<0:
            return -(a*a)*1.695
        return a*a*1.695

    def remove_zeroes_and_take_percentile(self, hist, percent):
        pairs = [(i, int(hist[i][0])) for i in range(len(hist))]
        pairs.sort(key=lambda x: x[1])
        pairs = [(i, v) for (i, v) in pairs if v > 0]

        # TODO: возможно стоит реализовать склейку взвешенных пар по яркости
        #  (если яркость +- 1 у соседа, то склеиваем их вместе и складываем или умножаем веса)
        base_threshold = 117
        weights = [int(self.negative_half_square(base_threshold - i) * (v ** 0.123)) for (i, v) in pairs]
        weighted = [(pair, weight) for pair, weight in zip(pairs, weights) if weight > 0]
        weighted.sort(key=lambda x: x[1], reverse=True)

        percentile = int(len(weighted) * percent / 100)
        try:
            return max(weighted[:percentile], key=lambda x: x[0][0])[0][0]
        except:
            return base_threshold

    def find_optimal_threshold(self, blurred, base_factor=None):
        hist = cv2.calcHist([blurred], [0], None, [256], [0, 256])
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(blurred)
        # the coefficients are optimal in most scenarios
        threshold = self.remove_zeroes_and_take_percentile(hist, percent=8.2)
        return max(threshold, min_val)

    def detect_contours(self, eye_thresholded):
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
                pupil = (cx, cy)

        return pupil, px, py, pw, ph, largest_area

    def detect(self, raw: numpy.ndarray):
        gray = self.get_eye_frame(raw)

        # blurred = self.blur_image(gray, blur=7)
        # blurred = self.blur_image(blurred, erode=2)
        # blurred = self.blur_image(blurred, blur=3)
        # blurred = self.blur_image(blurred, erode=2)

        blurred = self.blur_image(gray, blur=7)
        blurred = self.blur_image(blurred, blur=3)
        blurred = self.blur_image(blurred, dilate=2)
        blurred = self.blur_image(blurred, blur=3)
        blurred = self.blur_image(blurred, erode=3)

        #blurred = self.contrast_image(blurred, contrast=1.47, brightness=-3)
        threshold = self.find_optimal_threshold(blurred)
        self.threshold.add(threshold)
        thresholded_img = cv2.threshold(blurred, self.threshold.get(), 255, cv2.THRESH_BINARY_INV)[1]
        pupil_by_contours, px, py, pw, ph, area = self.detect_contours(thresholded_img)
        cv2.imshow('threshold', thresholded_img)
        cv2.waitKey(1)
        cv2.imshow('blur', blurred)
        cv2.waitKey(1)

        if pupil_by_contours is not None:
            self.x.add_if_diff_from_avg(pupil_by_contours[0])
            self.y.add_if_diff_from_avg(pupil_by_contours[1])
            self.pupil.array[:] = int(self.x.get()), int(self.y.get())
        else:
            self.pupil.invalidate()


class HoughCirclesPupilDetector(PupilDetector):
    def detect(self, raw):
        gray = self.get_eye_frame(raw)
        ex, ey = self._detect_area[0], self._detect_area[1]
        center = self.detect_circles(self.blur_image(gray, blur=7, dilate=5))
        self.pupil.array[:] = center.x + ex, center.y + ey

    def detect_circles(self, eye_frame: numpy.ndarray) -> Point:
        pupil_center = None
        max_radius = (eye_frame.shape[0] + eye_frame.shape[1] // 2)
        circles = cv2.HoughCircles(eye_frame, cv2.HOUGH_GRADIENT, 2.8, max_radius,
                                   param1=20, param2=8, minRadius=3, maxRadius=max_radius)
        max_radius = 1
        if circles is not None:
            for i in circles[0, :]:
                center = (i[0], i[1])
                radius = i[2]
                if radius > max_radius:
                    pupil_center = center
        if pupil_center:
            pupil_center = Point(*pupil_center).to_int()
        return pupil_center


class PupilLibraryDetector(PupilDetector):
    def mainloop(self):
        self.detector = IsophoteCurvature()
        super().mainloop()

    def detect(self, raw: numpy.ndarray):
        gray = self.get_eye_frame(raw)
        result = self.detector.locate(gray)
        self.pupil.array[:] = int(result[1] + self._detect_area[0]),\
                                                               int(result[0] + self._detect_area[1])