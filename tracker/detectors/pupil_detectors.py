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
    def in_process_init(self):
        self.dark_threshold = MovingAverageDenoiser(10)
        self.x = MovingAverageDenoiser(4)
        self.y = MovingAverageDenoiser(4)
        super().in_process_init()

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
                sticked = (pairs[(start + end) // 2][0], sum(value for brightness, value in pairs[start:end]))
                sticked_pairs.append(sticked)
            else:
                sticked_pairs.append(pairs[i])
            i+=1
        return sticked_pairs

    def find_darkest_area(self, brightness_count, mean_brightness=None):
        dynamic_range = len(brightness_count)
        shade_step = int(dynamic_range ** 0.4)

        brightness_count = self.stick_close_brightness(brightness_count, stick_count=shade_step) or brightness_count
        brightness_count.sort(key=lambda x: x[1])
        # TODO: base каким сделать, чтобы не сливались области, когда всё темно?
        base_threshold = mean_brightness or 117
        brightest = max(brightness_count, key=lambda x: x[0])[0] + 1
        darkest_weights = [int(v ** 2 * (brightest - i + 1) ** 13) for (i, v) in brightness_count]
        darkest_weighted = [(pair, weight) for pair, weight in zip(brightness_count, darkest_weights)]
        darkest_weighted.sort(key=lambda x: x[1], reverse=True)
        dark_threshold = darkest_weighted[0][0][0] if darkest_weighted else base_threshold
        return dark_threshold

    def find_optimal_threshold(self, blurred):
        resized = (blurred.shape[0] // 2, blurred.shape[1] // 2)
        if resized[0] < 5 or resized[1] < 5:
            self.pupil.invalidate()
            return 64
        blurred = cv2.resize(blurred, resized)
        hist = cv2.calcHist([blurred], [0], None, [256], [0, 256])
        # the coefficients are optimal in most scenarios
        #mean_brightness = numpy.mean(blurred, axis=(0, 1))
        brightness_count = [(i, int(hist[i][0])) for i in range(len(hist))]
        brightness_count.sort(key=lambda x: x[0])
        brightness_count = [(i, v) for (i, v) in brightness_count if v > 0]
        return self.find_darkest_area(brightness_count, 64)

    def detect_contours(self, dark_thresholded, gray):
        pupil = None
        eye_contours, _ = cv2.findContours(dark_thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        largest_area = 1
        best_circularity = 0.00001
        best_white = 0
        px, py, pw, ph = None, None, None, None
        for contour in eye_contours:
            contour = cv2.convexHull(contour)
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:  # чтобы избежать деления на ноль
                area = cv2.contourArea(contour)
                circularity = 4 * 3.14159 * (area / (perimeter**2))
                if circularity > best_circularity: # 0.85+ типично для зрачка
                    wmask = numpy.zeros(gray.shape, dtype=numpy.uint8)
                    # Белая область вокруг зрачка
                    (x, y), radius = cv2.minEnclosingCircle(contour)
                    cv2.circle(wmask, (int(x), int(y)), int(radius * 1.225), 255, -1)
                    # Черная область зрачка по его контуру
                    cv2.drawContours(wmask, [contour], -1, 0, -1)
                    max_white_around_contour= cv2.minMaxLoc(gray, mask=wmask)[1]
                    mask = numpy.zeros(gray.shape, dtype=numpy.uint8)
                    cv2.drawContours(mask, [contour], -1, 0, -1)
                    min_black_inside_contour = cv2.minMaxLoc(gray, mask=mask)[0]
                    if max_white_around_contour - min_black_inside_contour > best_white and area > largest_area / 6:
                        best_white = max_white_around_contour - min_black_inside_contour
                        M = cv2.moments(contour)
                        #area = M['m00']
                        #if area >= largest_area:
                        px, py, pw, ph = cv2.boundingRect(contour)
                        cx = int(M["m10"] / area)
                        cy = int(M["m01"] / area)
                        largest_area = area
                        best_circularity = circularity
                        pupil = (cx, cy)
        return pupil, px, py, pw, ph, largest_area

    def detect(self, raw: numpy.ndarray):
        try:
            gray = self.get_eye_frame(raw)
        except:
            self.pupil.invalidate()
            return
        # blurred = self.blur_image(gray, blur=7)
        # blurred = self.blur_image(blurred, erode=2)
        # blurred = self.blur_image(blurred, blur=3)
        # blurred = self.blur_image(blurred, erode=2)

        blurred = self.blur_image(gray, blur=13)
        #blurred = self.blur_image(blurred, blur=3)
        #blurred = self.blur_image(blurred, dilate=2)
        #blurred = self.blur_image(blurred, blur=3)
        blurred = self.blur_image(blurred, erode=5)
        blurred = self.blur_image(blurred, blur=5)

        blurred = self.contrast_image(blurred, contrast=1.8, brightness=-4)
        dark_threshold = self.find_optimal_threshold(blurred)
        self.dark_threshold.add(dark_threshold)
        dark_thresholded = cv2.threshold(blurred, self.dark_threshold.get(), 255, cv2.THRESH_BINARY_INV)[1]
        pupil_by_contours, px, py, pw, ph, area = self.detect_contours(dark_thresholded, blurred)
        #cv2.imshow('dark threshold', dark_thresholded)
        #cv2.imshow('blur', blurred)
        #cv2.waitKey(1)

        if pupil_by_contours is not None:
            self.x.add_if_diff_from_avg(pupil_by_contours[0])
            self.y.add_if_diff_from_avg(pupil_by_contours[1])
            self.pupil.array[:] = int(self.x.get() + self.detect_area.x1), int(self.y.get() + self.detect_area.y1)
        else:
            # PROBABLY BLINKED
            ...
        # else:
        #     self.pupil.invalidate()


class HoughCirclesPupilDetector(PupilDetector):
    def detect(self, raw):
        gray = self.get_eye_frame(raw)
        ex, ey = self.detect_area[0], self.detect_area[1]
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
        self.pupil.array[:] = int(result[1] + self.detect_area[0]),\
                                                               int(result[0] + self.detect_area[1])