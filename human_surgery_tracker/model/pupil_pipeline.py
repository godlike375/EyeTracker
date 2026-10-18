from multiprocessing import Process

import numpy

from tracker.camera import VideoAdapter
from tracker.detectors.pupil_detectors import DarkAreaPupilDetector
from tracker.detectors.haar_eye_detector import HaarCorrelationEyeValidator
from tracker.detectors.yolo_pupil_detector import YoloPupilDetector
from tracker.utils.coordinates import BoundingBox, Point
from tracker.utils.correlation_tracker import CorrelationBoxTracker
from tracker.utils.fps import FPSCounter, FPSLimiter
from tracker.utils.shared_objects import INITIAL_VALUE, SharedBox, SharedPoint

MIN_SEARCH_BOX = 16


class _PupilHolder:
    def __init__(self, pupil: SharedPoint):
        self.pupil = pupil


class _EyeHolder:
    def __init__(self, left_eye: SharedBox):
        self.left_eye = left_eye


class PupilPipeline:
    """Configurable pupil detection pipeline (experiment harness).

    Stages that can be toggled independently:
      * Haar cascade eye search (defines the search area for later stages);
      * YOLO segmentation pupil detector;
      * classic dark-area pupil detector (may refine inside the YOLO box);
      * inline dlib correlation tracking of the YOLO box to skip YOLO calls.

    If no valid ROI is provided, the whole frame is used as the search area.
    """

    def __init__(self, eyes_count: int, averaging_frames_count: int, detect_area: SharedBox,
                 video_adapter: VideoAdapter, target_fps: int,
                 use_haar: bool = True, use_yolo: bool = True, use_dark_area: bool = False,
                 yolo_model_path: str = None, yolo_conf: float = 0.25, yolo_imgsz: int = 192,
                 track_after_yolo: bool = True, yolo_track_frames: int = 10,
                 downscale_factor: float = 0.5, noise_threshold: float = 0.0):
        self.video_adapter = video_adapter.send_to_process()
        self.roi = detect_area
        self.fps = FPSLimiter(target_fps)
        self.use_haar = use_haar
        self.use_yolo = use_yolo
        self.use_dark_area = use_dark_area
        self.track_after_yolo = track_after_yolo
        self.track_frames = int(yolo_track_frames)

        self.eye_detect_area = SharedBox('i', INITIAL_VALUE)
        self.pupil_detect_area = SharedBox('i', INITIAL_VALUE)
        self.pupil = SharedPoint('i', INITIAL_VALUE)
        self.pupil.invalidate()

        self.haar = None
        if use_haar:
            self.haar = HaarCorrelationEyeValidator(
                eyes_count, averaging_frames_count, detect_area=self.eye_detect_area,
                video_adapter=video_adapter, target_fps=target_fps, new_process=False)
            self.eye_detector = self.haar
        else:
            empty_box = SharedBox('i', INITIAL_VALUE)
            empty_box.invalidate()
            self.eye_detector = _EyeHolder(empty_box)

        self.pupil_detector = _PupilHolder(self.pupil)

        self.yolo = None
        if use_yolo:
            self.yolo = YoloPupilDetector(
                model_path=yolo_model_path, conf=yolo_conf, imgsz=yolo_imgsz,
                detect_area=self.pupil_detect_area, video_adapter=video_adapter,
                target_fps=target_fps, new_process=False)

        self.dark = None
        if use_dark_area:
            self.dark = DarkAreaPupilDetector(
                detect_area=self.pupil_detect_area, video_adapter=video_adapter,
                target_fps=target_fps, new_process=False)

        self.tracker = None
        self._tracker_cfg = dict(downscale_factor=downscale_factor, noise_threshold=noise_threshold)
        self.tracking_active = False
        self.track_frames_left = 0

        self.process = None
        self.fps_cnt = FPSCounter()

    def start_process(self):
        self.process = Process(target=self.in_process_init, daemon=True)
        self.process.start()
        return self.process

    def stop_process(self):
        if self.process is not None:
            try:
                self.process.terminate()
                self.process.join(timeout=2)
                if self.process.is_alive():
                    self.process.kill()
            except (AttributeError, ValueError):
                pass
        self.process = None

    def in_process_init(self):
        if self.track_after_yolo:
            self.tracker = CorrelationBoxTracker(**self._tracker_cfg)
        if self.haar:
            self.haar.in_process_init()
        if self.yolo:
            self.yolo.in_process_init()
        if self.dark:
            self.dark.in_process_init()
        self.mainloop()

    def mainloop(self):
        self.video_adapter.setup_video_frame()
        while True:
            if not self.fps.able_to_execute():
                self.fps.throttle()
            self.fps_cnt.count_frame()
            if self.fps_cnt.able_to_calculate():
                print(f'pupil pipeline fps {self.fps_cnt.calculate()}')
            self.detect(self.video_adapter.get_copy_video_frame())

    def detect(self, raw: numpy.ndarray):
        height, width = raw.shape[:2]
        self._set_search_area(self.eye_detect_area, height, width)

        yolo_point = None
        tracked = self._track_step(raw)
        if tracked is not None:
            yolo_point = tracked

        if not (self.tracker and self.tracking_active):
            yolo_point = self._detect_step(raw)

        dark_point = None
        if self.dark and not self.tracking_active:
            if self.yolo and self.yolo.last_box.is_valid():
                self._copy_box(self.yolo.last_box, self.pupil_detect_area)
            self.dark.detect(raw)
            if self.dark.pupil.is_valid:
                dark_point = Point(self.dark.pupil.x, self.dark.pupil.y)

        final = self._fuse(yolo_point, dark_point)
        if final is None:
            self.pupil.invalidate()
        else:
            self.pupil.array[:] = int(final.x), int(final.y)

    def _track_step(self, raw: numpy.ndarray):
        if self.tracker is None or not self.tracking_active:
            return None
        if self.track_frames_left <= 0:
            self.tracking_active = False
            return None
        self.tracker.update(raw)
        self.track_frames_left -= 1
        return self.tracker.center

    def _detect_step(self, raw: numpy.ndarray):
        if self.haar:
            self.haar.detect(raw)
        if self.haar and self._box_is_reasonable(self.eye_detector.left_eye):
            self._copy_box(self.eye_detector.left_eye, self.pupil_detect_area)
        else:
            self._copy_box(self.eye_detect_area, self.pupil_detect_area)

        if not self.yolo:
            return None
        self.yolo.detect(raw)
        if not self.yolo.pupil.is_valid:
            return None

        point = Point(self.yolo.pupil.x, self.yolo.pupil.y)
        if self.tracker is not None and self.yolo.last_box.is_valid():
            self.tracker.reset(BoundingBox(
                self.yolo.last_box.x1, self.yolo.last_box.y1,
                self.yolo.last_box.x2, self.yolo.last_box.y2))
            self.tracking_active = True
            self.track_frames_left = self.track_frames
        return point

    def _fuse(self, yolo_point, dark_point):
        if yolo_point is not None:
            return yolo_point
        return dark_point

    def _box_is_reasonable(self, box: SharedBox) -> bool:
        if not box.is_valid():
            return False
        return (box.x2 - box.x1) >= MIN_SEARCH_BOX and (box.y2 - box.y1) >= MIN_SEARCH_BOX

    def _set_search_area(self, area: SharedBox, height: int, width: int):
        roi = self.roi
        if roi.is_valid() and roi.x2 > roi.x1 and roi.y2 > roi.y1:
            area.x1, area.y1 = max(0, roi.x1), max(0, roi.y1)
            area.x2, area.y2 = min(width, roi.x2), min(height, roi.y2)
        else:
            area.x1, area.y1, area.x2, area.y2 = 0, 0, width, height

    def _copy_box(self, src: SharedBox, dst: SharedBox):
        dst.x1, dst.y1 = src.x1, src.y1
        dst.x2, dst.y2 = src.x2, src.y2
