from multiprocessing import Process

import numpy

from tracker.camera import VideoAdapter
from tracker.detectors.haar_eye_detector import HaarCorrelationEyeValidator
from tracker.detectors.pupil_detectors import DarkAreaPupilDetector
from tracker.utils.fps import FPSLimiter, FPSCounter
from tracker.utils.shared_objects import SharedBox, INITIAL_VALUE


class EyePupilDetector:
    def __init__(self, eyes_count: int, averaging_frames_count: int, eye_detect_area: SharedBox, video_adapter: VideoAdapter,
                                                        target_fps: int):
        self.video_adapter = video_adapter
        self.fps = FPSLimiter(target_fps)
        self.eye_detector = HaarCorrelationEyeValidator(eyes_count, averaging_frames_count, detect_area=eye_detect_area,
                                                        video_adapter=video_adapter, target_fps=target_fps, new_process=False)
        self.pupil_detect_area = SharedBox('i', INITIAL_VALUE)
        self.pupil_detector = DarkAreaPupilDetector(detect_area=self.pupil_detect_area, video_adapter=video_adapter,
                                                    target_fps=target_fps, new_process=False)
        self.process = None
        self.fps_cnt = FPSCounter()

    def start_process(self):
        self.process = Process(target=self.in_process_init, daemon=True)
        self.process.start()
        return self.process

    def stop_process(self):
        if self.process is not None:
            self.process.terminate()
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.kill()
        self.process = None

    def in_process_init(self):
        self.eye_detector.in_process_init()
        self.pupil_detector.in_process_init()
        self.mainloop()

    def mainloop(self):
        self.video_adapter.setup_video_frame()
        while True:
            if not self.fps.able_to_execute():
                self.fps.throttle()
            self.fps_cnt.count_frame()
            if self.fps_cnt.able_to_calculate():
                print(self.fps_cnt.calculate())
            self.detect(self.video_adapter.get_copy_video_frame())

    def detect(self, raw: numpy.ndarray):
        self.eye_detector.detect(raw)
        self.pupil_detect_area.left_top.array[:] = self.eye_detector.left_eye.left_top.array[:]
        self.pupil_detect_area.right_bottom.array[:] = self.eye_detector.left_eye.right_bottom.array[:]
        self.pupil_detector.detect(raw)