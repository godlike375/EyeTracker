from multiprocessing import Process
from statistics import mean

from tracker.detectors.detectors import Detector
from tracker.detectors.haar_eye_detector import HaarEyeValidator
from tracker.detectors.mediapipe_detector import MediapipeMeshDetector
from tracker.detectors.pupil_detectors import DarkAreaPupilDetector
from tracker.utils.coordinates import Point, calc_center, BoundingBox
from tracker.utils.fps import FPSLimiter
from tracker.utils.shared_objects import SharedBox, SharedPoint, SharedVector

Priority = int

class DetectorsManager:
    def __init__(self, detect_area: SharedBox, target_fps: int, #haar_validator: HaarEyeValidator,
                 mesh_detector: MediapipeMeshDetector):#, dark_area_detector: DarkAreaPupilDetector):
        self.detect_area = detect_area
        #self.haar = haar_validator
        self.mesh = mesh_detector
        #self.dark = dark_area_detector
        self.left_eye = SharedBox('i', -1)
        self.right_eye = SharedBox('i', -1)
        self.left_pupil = SharedPoint('i', -1)
        self.right_pupil = SharedPoint('i', -1)
        self.fps = FPSLimiter(target_fps)

    def start_process(self):
        process = Process(target=self.mainloop, daemon=True)
        process.start()
        return process

    def mainloop(self):
        while True:
            if not self.fps.able_to_execute():
                self.fps.throttle()

                mesh_eyes = self.mesh.detect_eyes()
                if any([not eye.is_valid() for eye in mesh_eyes]):
                    continue

                moved = mesh_eyes[0] + self.detect_area.left_top
                self.left_eye.left_top.array[:] = moved.x1, moved.y1
                self.left_eye.right_bottom.array[:] = moved.x2, moved.y2

                moved = mesh_eyes[1] + self.detect_area.left_top
                self.right_eye.left_top.array[:] = moved.x1, moved.y1
                self.right_eye.right_bottom.array[:] = moved.x2, moved.y2

                # haar_eyes = self.haar.detect_eyes()
                # if all([not eye.is_valid() for eye in haar_eyes]):
                #     continue

                # (left_haar, right_haar) = (haar_eyes[0], haar_eyes[1]) \
                #     if haar_eyes[0].x1 < haar_eyes[1].x1 else (haar_eyes[1], haar_eyes[0])
                #
                # if left_eye[2].is_valid() and left_eye[1].is_valid()\
                #         and left_eye[2].center.calc_distance(left_eye[1].center) <= 10:
                #     self.left_eye.left_top.array[:] = left_eye[1].left_top
                #     self.left_eye.right_bottom = left_eye[1].right_bottom

                # TODO: к детекторам прибавлять координаты detect_area
                #  (они не должны знать, что находятся в ограниченной области)

                pupils = self.mesh.detect_pupils()

                moved = pupils[0] + self.detect_area.left_top
                self.left_pupil.array[:] = moved.x, moved.y

                moved = pupils[1] + self.detect_area.left_top
                self.right_pupil.array[:] = moved.x, moved.y

                # for priority, detector in self.detetors.items():
                #     if detector.can_detect_pupil():
                #         pupil = detector.detect_pupil()
                #         left_centers = [calc_center(Point(box.x1, box.y1), Point(box.x2, box.y2)).x
                #                         for box in left_eye.values()]
                #         right_centers = [calc_center(Point(box.x1, box.y1), Point(box.x2, box.y2)).x
                #                         for box in right_eye.values()]
                #         if abs(pupil.x - mean(left_centers)) < abs(pupil.x - mean(right_centers)):
                #             left_pupil[priority] = pupil
                #         else:
                #             right_pupil[priority] = pupil

                # TODO: подобрать значение вместо 10



    def detect(self) -> tuple[tuple[SharedBox, SharedBox], tuple[SharedPoint, SharedPoint]]:
        return (self.left_eye, self.right_eye), (self.left_pupil, self.right_pupil)
