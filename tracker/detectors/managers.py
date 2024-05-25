from tracker.detectors.detectors import PupilDetector
from tracker.utils.coordinates import Point

Priority = int

class PupilDetectorManager:
    def __init__(self, detectors: dict[Priority, PupilDetector] = None):
        #super().__init__()
        self.detectors = detectors

    def detect(self) -> Point:
        for detector in self.detectors.values():
            return Point(detector.coordinates[0], detector.coordinates[1])