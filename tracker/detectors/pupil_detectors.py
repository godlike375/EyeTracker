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
        self.x = MovingAverageDenoiser(4)
        self.y = MovingAverageDenoiser(4)
        super().mainloop()

    def stick_close_brightness(self, pairs, stick_threshold = 1, stick_count = 3):
        sticked_pairs = []
        # TODO: уменьшать разрешение, чтобы убирать шумы, обобщать контуры
        i = 0
        while i < len(pairs) - 1:
            start = i
            end = i
            while i < len(pairs) - 1 and end - start < stick_count and abs(pairs[i][0] - pairs[i + 1][0]) <= stick_threshold:
                i+= 1
                end = i
            if start != end:
                sticked = (pairs[end][0], sum(value for brightness, value in pairs[start:end]))
                sticked_pairs.append(sticked)
            else:
                sticked_pairs.append(pairs[i])
            i+=1
        return sticked_pairs

    def remove_zeroes_and_take_darkest(self, hist, mean_brightness=None):
        brightness_count = [(i, int(hist[i][0])) for i in range(len(hist))]
        brightness_count.sort(key=lambda x: x[0])
        brightness_count = [(i, v) for (i, v) in brightness_count if v > 0]
        dynamic_range = len(brightness_count)
        shade_step = int(dynamic_range ** 0.25)

        brightness_count = self.stick_close_brightness(brightness_count, stick_count=shade_step) or brightness_count
        brightness_count.sort(key=lambda x: x[1])
        # TODO: base каким сделать, чтобы не сливались области, когда всё темно?
        base_threshold = mean_brightness or 117
        max_intensity = max(brightness_count, key=lambda x: x[0])[0] + 1
        weights = [int(v / ((i+1)/max_intensity) ** 15) for (i, v) in brightness_count]
        weighted = [(pair, weight) for pair, weight in zip(brightness_count, weights) if weight > 0]
        weighted.sort(key=lambda x: x[1], reverse=True)
        if weighted:
            return weighted[0][0][0]
        else:
            return base_threshold

    def find_optimal_threshold(self, blurred):
        blurred = cv2.resize(blurred, (blurred.shape[0] // 2, blurred.shape[1] // 2))
        hist = cv2.calcHist([blurred], [0], None, [256], [0, 256])
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(blurred)
        # the coefficients are optimal in most scenarios
        #mean_brightness = numpy.mean(blurred, axis=(0, 1))
        threshold = self.remove_zeroes_and_take_darkest(hist, 64)
        return max(threshold, min_val)

    def detect_contours(self, eye_thresholded):
        pupil = None
        eye_contours, _ = cv2.findContours(eye_thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        largest_area = 1
        best_circularity = 0.00001
        px, py, pw, ph = None, None, None, None
        for contour in eye_contours:
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:  # чтобы избежать деления на ноль
                area = cv2.contourArea(contour)
                circularity = 4 * 3.14159 * (area / (perimeter**2))
                if circularity > best_circularity and circularity > 0.825: # 0.85+ типично для зрачка
                    M = cv2.moments(contour)
                    #area = M['m00']
                    #if area >= largest_area:
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

        blurred = self.blur_image(gray, blur=9)
        #blurred = self.blur_image(blurred, blur=3)
        blurred = self.blur_image(blurred, dilate=2)
        blurred = self.blur_image(blurred, blur=3)
        blurred = self.blur_image(blurred, erode=4)
        blurred = self.blur_image(blurred, blur=3)

        #blurred = self.contrast_image(blurred, contrast=1.47, brightness=-3)
        threshold = self.find_optimal_threshold(blurred)
        self.threshold.add(threshold)
        thresholded_img = cv2.threshold(blurred, self.threshold.get(), 255, cv2.THRESH_BINARY_INV)[1]
        pupil_by_contours, px, py, pw, ph, area = self.detect_contours(thresholded_img)
        # cv2.imshow('threshold', thresholded_img)
        # cv2.waitKey(1)
        # cv2.imshow('blur', blurred)
        # cv2.waitKey(1)

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