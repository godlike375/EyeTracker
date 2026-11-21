import math
import time
from multiprocessing import Array, Process
from multiprocessing.shared_memory import SharedMemory

import cv2
import numpy
import numpy as np
from scipy.ndimage import gaussian_filter1d

from tracker.detectors.detectors import Detector, PupilDetector
from tracker.detectors.jonnedtc import IsophoteCurvature
from tracker.utils.denoise import MovingAverageDenoiser
from tracker.utils.image_processing import blur_image, contrast_image
from tracker.utils.coordinates import Point


class DarkAreaPupilDetector(PupilDetector):
    def __init__(self, *args, invalidate_on_miss: bool = False,
                 center_weight: float = 0.7, center_sigma: float = 0.35, **kwargs):
        self.invalidate_on_miss = invalidate_on_miss
        self.center_weight = float(center_weight)
        self.center_sigma = float(center_sigma)
        super().__init__(*args, **kwargs)

    def in_process_init(self):
        #self.dark_threshold = MovingAverageDenoiser(2)
        self.x = MovingAverageDenoiser(3)
        self.y = MovingAverageDenoiser(3)
        super().in_process_init()

    def center_factor(self, x: float, y: float, height: int, width: int) -> float:
        """Favour contours near the ROI centre (the eye is usually centred)."""
        if self.center_weight <= 0.0:
            return 1.0
        sigma = max(1.0, self.center_sigma * min(height, width))
        dist2 = (x - width / 2.0) ** 2 + (y - height / 2.0) ** 2
        weight = math.exp(-0.5 * dist2 / (sigma ** 2))
        return (1.0 - self.center_weight) + self.center_weight * weight

    def find_optimal_threshold(self, blurred):
        resized = (blurred.shape[0] // 2, blurred.shape[1] // 2)
        if resized[0] < 5 or resized[1] < 5:
            self.pupil.invalidate()
            return 64
        blurred = cv2.resize(blurred, resized)
        hist = np.histogram(blurred, bins=256, range=[0, 256])[0]
        smoothed_hist = gaussian_filter1d(hist, sigma=1)
        for i in range(1, 252):
            if smoothed_hist[i - 1] > smoothed_hist[i] < smoothed_hist[i + 3]:
                dark_threshold = i
                break
        else:
            dark_threshold = 64

        return dark_threshold

    def detect_contours(self, dark_thresholded, gray):
        height, width = gray.shape[:2]
        eye_contours, _ = cv2.findContours(dark_thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        hulls = []
        largest_area = 1
        for contour in eye_contours:
            contour = cv2.convexHull(contour)
            area = cv2.contourArea(contour)
            largest_area = max(largest_area, area)
            hulls.append((contour, area))

        best_pupil = None
        best_score = 0.0
        px, py, pw, ph = None, None, None, None
        for contour, area in hulls:
            if area <= largest_area / 6:
                continue
            perimeter = cv2.arcLength(contour, True)
            if perimeter <= 0:
                continue
            circularity = 4 * math.pi * area / (perimeter ** 2)
            moments = cv2.moments(contour)
            if moments['m00'] == 0:
                continue
            cx = moments['m10'] / moments['m00']
            cy = moments['m01'] / moments['m00']
            score = circularity * self.center_factor(cx, cy, height, width)
            if score > best_score:
                best_score = score
                best_pupil = (int(cx), int(cy))
                px, py, pw, ph = cv2.boundingRect(contour)
        return best_pupil, px, py, pw, ph, largest_area

    def detect(self, raw: numpy.ndarray):
        try:
            gray = self.get_eye_frame(raw)
        except:
            self.pupil.invalidate()
            return
        blurred = blur_image(gray, blur=25)
        blurred = blur_image(blurred, erode=8)

        blurred = contrast_image(blurred, contrast=0.7, brightness=18)
        dark_threshold = self.find_optimal_threshold(blurred)
        dark_thresholded = cv2.threshold(blurred, dark_threshold, 255, cv2.THRESH_BINARY_INV)[1]
        pupil_by_contours, px, py, pw, ph, area = self.detect_contours(dark_thresholded, blurred)

        if pupil_by_contours is not None:
            self.x.add_if_diff_from_avg(pupil_by_contours[0], diff_by=0.5)
            self.y.add_if_diff_from_avg(pupil_by_contours[1])
            self.pupil.array[:] = int(self.x.get() + self.detect_area.x1), int(self.y.get() + self.detect_area.y1)
        else:
            # PROBABLY BLINKED: keep the last known position by default, so that
            # consumers don't see a spurious invalidation on a single missed frame.
            if self.invalidate_on_miss:
                self.pupil.invalidate()
        # else:
        #     self.pupil.invalidate()


class HoughCirclesPupilDetector(PupilDetector):
    def detect(self, raw):
        gray = self.get_eye_frame(raw)
        ex, ey = self.detect_area[0], self.detect_area[1]
        center = self.detect_circles(blur_image(gray, blur=7, dilate=5))
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