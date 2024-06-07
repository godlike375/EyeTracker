import time
from multiprocessing import Array, Process
from multiprocessing.shared_memory import SharedMemory

import cv2
import numpy

from tracker.detectors.detectors import PupilDetector
from tracker.detectors.jonnedtc import GradientIntersect
from tracker.object_tracker import FPS_120
from tracker.utils.coordinates import Point
from tracker.utils.fps import FPSLimiter


class DarkAreaPupilDetector(PupilDetector):
    def detect_contours(self, eye_thresholded, ex, ey):
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

    def detect(self, raw: numpy.ndarray):
        ex, ey = self.eye_box[0], self.eye_box[1]
        gray = self.get_eye_frame(raw)
        blurred = self.blur_image(gray, gaussian=7, erode=3) # tested, works most accurate
        threshold = self.find_optimal_threshold(blurred)
        thresholded_img = cv2.threshold(blurred, threshold, 255, cv2.THRESH_BINARY_INV)[1]
        pupil_by_contours, px, py, pw, ph, area = self.detect_contours(thresholded_img, ex, ey)
        # cv2.imshow('threshold', thresholded_img)
        # cv2.waitKey(1)

        if pupil_by_contours is not None:
            self.pupil_coordinates[0], self.pupil_coordinates[1] = pupil_by_contours


class HoughCirclesPupilDetector(PupilDetector):
    def detect(self, raw):
        gray = self.get_eye_frame(raw)
        ex, ey = self.eye_box[0], self.eye_box[1]
        center = self.detect_circles(self.blur_image(gray, gaussian=7, dilate=5))
        self.pupil_coordinates[0], self.pupil_coordinates[1] = center.x + ex, center.y + ey

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
        raw = numpy.ndarray((*self.resolution, 3), dtype=numpy.uint8, buffer=self.current_frame.buf)
        detector = GradientIntersect()
        fps = FPSLimiter(120)

        eye_frame = raw[self.eye_box[1]: self.eye_box[3], self.eye_box[0]: self.eye_box[2]]
        gray = cv2.cvtColor(eye_frame, cv2.COLOR_BGR2GRAY)
        ex, ey = self.eye_box[0], self.eye_box[1]
        result = detector.locate(gray)
        self.pupil_coordinates[0], self.pupil_coordinates[1] = int(result[1] + ex), int(result[0] + ey)

        while True:
            if not fps.able_to_execute():
                time.sleep(FPS_120)
                continue
            eye_frame = raw[self.eye_box[1]: self.eye_box[3], self.eye_box[0]: self.eye_box[2]]
            gray = cv2.cvtColor(eye_frame, cv2.COLOR_BGR2GRAY)
            ex, ey = self.eye_box[0], self.eye_box[1]
            result = detector.track(gray, result)
            self.pupil_coordinates[0], self.pupil_coordinates[1] = int(result[1] + ex), int(result[0] + ey)