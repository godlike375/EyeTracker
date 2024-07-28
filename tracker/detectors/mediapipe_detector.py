import mediapipe as mp
import numpy

from tracker.utils.coordinates import enclosing_box_of
from tracker.utils.shared_objects import SharedPoint

face_detector = mp.solutions.face_mesh

from tracker.detectors.detectors import FaceMeshDetector
from tracker.utils.denoise import MovingAverageDenoiser


right_of_left = 133
left_of_left = 33
bottom_of_top_left = 159
top_of_left = 27
top_of_bottom_left = 145
bottom_of_left = 23

right_of_right = 263
left_of_right = 362
bottom_of_top_right = 386
top_of_right = 257
top_of_bottom_right = 374
bottom_of_right = 253

left_pupil = 468
right_pupil = 473

# top_face = 10
# bottom_face = 152


class MediapipeMeshDetector(FaceMeshDetector):

    def mainloop(self):
        self.left = [MovingAverageDenoiser(2), MovingAverageDenoiser(2), MovingAverageDenoiser(2), MovingAverageDenoiser(2)]
        self.right = [MovingAverageDenoiser(2), MovingAverageDenoiser(2), MovingAverageDenoiser(2), MovingAverageDenoiser(2)]
        self.detector = face_detector.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.0000001,
            min_tracking_confidence=0.0000001
        )
        super().mainloop()

    def detect(self, raw: numpy.ndarray):
        frame = self.get_eye_rgb_frame(raw)
        img_h, img_w = frame.shape[:2]
        #frame.flags.writable = False
        results = self.detector.process(frame)
        #frame.flags.writable = True
        if results.multi_face_landmarks:
            pts = numpy.array(
                [numpy.multiply([p.x, p.y, p.z], [img_w, img_h, img_w])
                 for p in results.multi_face_landmarks[0].landmark])

            for i, p in enumerate(pts):
                self.mesh[i].array[:] = p[:]

            # TODO: находить самые левые верхние и правые нижние координаты нормально

            left_eye_points = [self.mesh[left_of_left].to_point(),
                               (self.mesh[top_of_left].to_point() + self.mesh[bottom_of_top_left].to_point()) / 2,
                               self.mesh[right_of_left].to_point(),
                               (self.mesh[bottom_of_left].to_point() + self.mesh[top_of_bottom_left].to_point()) / 2]
            left_box = enclosing_box_of(left_eye_points)

            self.left_eye.left_top.array[:] = int(left_box.x1), int(left_box.y1)
            self.left_eye.right_bottom.array[:] = int(left_box.x2), int(left_box.y2)

            right_eye_points = [self.mesh[left_of_right].to_point(),
                                (self.mesh[top_of_right].to_point() + self.mesh[bottom_of_top_right].to_point()) / 2,
                               self.mesh[right_of_right].to_point(),
                               (self.mesh[bottom_of_right].to_point() + self.mesh[top_of_bottom_right].to_point()) / 2]
            right_box = enclosing_box_of(right_eye_points)

            self.right_eye.left_top.array[:] = int(right_box.x1), int(right_box.y1)
            self.right_eye.right_bottom.array[:] = int(right_box.x2), int(right_box.y2)

            self.left_pupil.array[:] = int(self.mesh[left_pupil].x), int(self.mesh[left_pupil].y)
            self.right_pupil.array[:] = int(self.mesh[right_pupil].x), int(self.mesh[right_pupil].y)
        else:
            self.left_eye.invalidate()
            self.right_eye.invalidate()
            self.left_pupil.invalidate()
            self.right_pupil.invalidate()

        # TODO: reset detector

    def detect_pupils(self) -> tuple[SharedPoint, SharedPoint]: return self.left_pupil, self.right_pupil