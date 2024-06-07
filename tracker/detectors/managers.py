from multiprocessing import Array

from tracker.detectors.detectors import PupilDetector, EyeDetector
from tracker.protocol import Coordinates, BoundingBox
from tracker.utils.coordinates import Point

Priority = int

class DetectorManager:
    def __init__(self, manual_box: Array, eye_detectors: dict[Priority, EyeDetector] = None):
        self.manual_box = manual_box
        self.eye_detectors = eye_detectors
        self.pupil_detectors = dict()

    def add_pupil_detectors(self, pupil_detectors: dict[Priority, PupilDetector] = None):
        self.pupil_detectors = pupil_detectors

    def detect(self) -> tuple[BoundingBox, Point]:
        eye = None
        for detector in self.eye_detectors.values():
            eye = BoundingBox(detector.eye_coordinates[0], detector.eye_coordinates[1],
                               detector.eye_coordinates[2], detector.eye_coordinates[3])
        pupil = None
        for detector in self.pupil_detectors.values():
            pupil = Point(detector.pupil_coordinates[0], detector.pupil_coordinates[1])

        return eye, pupil
