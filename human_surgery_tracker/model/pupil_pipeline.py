from collections import deque
from multiprocessing import Process, Value

import numpy

from tracker.camera import VideoAdapter
from tracker.detectors.pupil_detectors import DarkAreaPupilDetector
from tracker.detectors.haar_eye_detector import HaarCorrelationEyeValidator
from tracker.detectors.yolo_pupil_detector import YoloPupilDetector
from tracker.utils.coordinates import BoundingBox, Point
from tracker.utils.correlation_tracker import CorrelationBoxTracker
from tracker.utils.fps import FPSCounter, FPSLimiter
from tracker.utils.shared_objects import INITIAL_VALUE, SharedBox, SharedPoint, SharedFlag

MIN_SEARCH_BOX = 16
HAAR_INTERVAL_FRAMES = 15


class MovingAveragePoint:
    """Running moving-average filter for 2D pupil coordinates across N frames."""
    def __init__(self, count: int = 1):
        self.count = max(1, int(count))
        self.buf_x = deque()
        self.buf_y = deque()

    def reset(self):
        self.buf_x.clear()
        self.buf_y.clear()

    def update(self, x: float, y: float) -> tuple[float, float]:
        if self.count <= 1:
            return x, y
        if not self.buf_x:
            # Pre-fill buffer to avoid initial ramp-up delay after eye re-acquisition
            for _ in range(self.count):
                self.buf_x.append(x)
                self.buf_y.append(y)
            return x, y
        self.buf_x.popleft()
        self.buf_y.popleft()
        self.buf_x.append(x)
        self.buf_y.append(y)
        return sum(self.buf_x) / self.count, sum(self.buf_y) / self.count


class MovingAverageBox:
    """Running moving-average filter for 4D bounding box coordinates across N frames."""
    def __init__(self, count: int = 1):
        self.count = max(1, int(count))
        self.buffers = [deque(), deque(), deque(), deque()]

    def reset(self):
        for b in self.buffers:
            b.clear()

    def update(self, x1: float, y1: float, x2: float, y2: float) -> tuple[int, int, int, int]:
        coords = (x1, y1, x2, y2)
        if self.count <= 1:
            return int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))
        if not self.buffers[0]:
            for i, c in enumerate(coords):
                for _ in range(self.count):
                    self.buffers[i].append(c)
            return int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))

        smoothed = []
        for i, c in enumerate(coords):
            self.buffers[i].popleft()
            self.buffers[i].append(c)
            smoothed.append(sum(self.buffers[i]) / self.count)
        return (
            int(round(smoothed[0])),
            int(round(smoothed[1])),
            int(round(smoothed[2])),
            int(round(smoothed[3])),
        )


class _PupilHolder:
    def __init__(self, pupil: SharedPoint, pupil_box: SharedBox = None,
                 dark_pupil: SharedPoint = None, is_tracking: SharedFlag = None):
        self.pupil = pupil
        self.pupil_box = pupil_box
        self.dark_pupil = dark_pupil
        self._is_tracking = is_tracking

    @property
    def is_tracking(self) -> bool:
        if self._is_tracking is None:
            return False
        return bool(self._is_tracking.get() if hasattr(self._is_tracking, 'get') else self._is_tracking)


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
                 use_haar: bool = False, use_yolo: bool = True,
                 use_dark_area: bool = False, dark_invalidate_on_miss: bool = False,
                 dark_center_weight: float = 0.7, dark_box_scale: float = 2.0,
                 yolo_model_path: str = None, yolo_conf: float = 0.25, yolo_imgsz: int = 640,
                 yolo_fit_ellipse: bool = True, yolo_associate: bool = True,
                 track_after_yolo: bool = True, yolo_track_frames: int = 10,
                 downscale_factor: float = 0.5, noise_threshold: float = 0.0):
        self.video_adapter = video_adapter.send_to_process()
        self.roi = detect_area
        self.fps = FPSLimiter(target_fps)
        self.use_haar = use_haar
        self.use_yolo = use_yolo
        self.use_dark_area = use_dark_area
        self.dark_box_scale = float(dark_box_scale)
        self.track_after_yolo = track_after_yolo
        self.track_frames = int(yolo_track_frames)
        self.averaging_frames_count = max(1, int(averaging_frames_count))
        self.smooth_pupil = MovingAveragePoint(self.averaging_frames_count)
        self.smooth_box = MovingAverageBox(self.averaging_frames_count)

        self.eye_detect_area = SharedBox('i', INITIAL_VALUE)
        self.pupil_detect_area = SharedBox('i', INITIAL_VALUE)
        self.dark_detect_area = SharedBox('i', INITIAL_VALUE)
        self.pupil = SharedPoint('i', INITIAL_VALUE)
        self.pupil.invalidate()
        self.pupil_box = SharedBox('i', INITIAL_VALUE)
        self.pupil_box.invalidate()
        self.dark_pupil = SharedPoint('i', INITIAL_VALUE)
        self.dark_pupil.invalidate()
        self.is_tracking = SharedFlag(False)

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

        self.pupil_detector = _PupilHolder(self.pupil, self.pupil_box, self.dark_pupil, self.is_tracking)

        self.yolo = None
        if use_yolo:
            self.yolo = YoloPupilDetector(
                model_path=yolo_model_path, conf=yolo_conf, imgsz=yolo_imgsz,
                use_ellipse=yolo_fit_ellipse, associate=yolo_associate,
                detect_area=self.pupil_detect_area, video_adapter=video_adapter,
                target_fps=target_fps, new_process=False)

        self.dark = None
        if use_dark_area:
            self.dark = DarkAreaPupilDetector(
                detect_area=self.dark_detect_area, video_adapter=video_adapter,
                target_fps=target_fps, new_process=False,
                invalidate_on_miss=dark_invalidate_on_miss,
                center_weight=dark_center_weight)

        self.tracker = None
        self._tracker_cfg = dict(downscale_factor=downscale_factor, noise_threshold=noise_threshold)
        self.tracking_active = False
        self.track_frames_left = 0

        self.eye_tracker = None
        self.eye_tracker_active = False
        self.haar_frame_counter = 0

        self.process = None
        self.fps_cnt = FPSCounter()
        self.fps_value = Value('f', 0.0)

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
            self.eye_tracker = CorrelationBoxTracker(**self._tracker_cfg)
            self.eye_tracker_active = False
            self.haar_frame_counter = HAAR_INTERVAL_FRAMES
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
                fps = self.fps_cnt.calculate()
                self.fps_value.value = fps
                print(f'pupil pipeline fps {fps}')
            self.detect(self.video_adapter.get_copy_video_frame())

    def detect(self, raw: numpy.ndarray):
        height, width = raw.shape[:2]
        self._set_search_area(self.eye_detect_area, height, width)
        self._update_eye_tracker(raw)

        yolo_point = None
        tracked = self._track_step(raw)
        currently_tracking = False
        if tracked is not None:
            yolo_point = tracked
            currently_tracking = True

        if not (self.tracker and self.tracking_active):
            yolo_point = self._detect_step(raw)
            currently_tracking = False

        # Active bounding box for DarkArea refinement inside a 2x-3x crop
        active_box = None
        if self.tracking_active and self.tracker and self.tracker.box:
            active_box = self.tracker.box
        elif self.yolo and self.yolo.last_box.is_valid():
            active_box = self.yolo.last_box

        dark_point = None
        if self.dark and active_box is not None:
            if self._update_dark_area(active_box, width, height, scale=self.dark_box_scale):
                self.dark.detect(raw)
                if self.dark.pupil.is_valid:
                    dark_point = Point(self.dark.pupil.x, self.dark.pupil.y)

        final = self._fuse(yolo_point, dark_point)
        if final is None:
            self.pupil.invalidate()
            self.pupil_box.invalidate()
            self.dark_pupil.invalidate()
            self.is_tracking.set(False)
            self.smooth_pupil.reset()
            self.smooth_box.reset()
        else:
            sx, sy = self.smooth_pupil.update(final.x, final.y)
            self.pupil.array[:] = int(round(sx)), int(round(sy))
            self.is_tracking.set(currently_tracking)
            if active_box is not None:
                bx1, by1, bx2, by2 = self.smooth_box.update(
                    active_box.x1, active_box.y1, active_box.x2, active_box.y2
                )
                self.pupil_box.x1 = bx1
                self.pupil_box.y1 = by1
                self.pupil_box.x2 = bx2
                self.pupil_box.y2 = by2
            else:
                self.pupil_box.invalidate()
                self.smooth_box.reset()

            if dark_point is not None:
                self.dark_pupil.array[:] = int(dark_point.x), int(dark_point.y)
            else:
                self.dark_pupil.invalidate()

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
            self._update_eye_area(raw)
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

    def _update_eye_area(self, raw: numpy.ndarray):
        self.haar_frame_counter += 1
        if self.haar_frame_counter >= HAAR_INTERVAL_FRAMES:
            self.haar_frame_counter = 0
            self.haar.detect(raw)
            if self._box_is_reasonable(self.eye_detector.left_eye):
                self._seed_eye_tracker(self.eye_detector.left_eye)
        if self.eye_tracker_active and self._copy_bbox(self.eye_tracker.box, self.pupil_detect_area):
            return
        self._copy_box(self.eye_detect_area, self.pupil_detect_area)

    def _update_eye_tracker(self, raw: numpy.ndarray):
        if self.eye_tracker is None or not self.eye_tracker_active:
            return
        _, _, lost = self.eye_tracker.update(raw)
        if lost:
            self.eye_tracker_active = False

    def _seed_eye_tracker(self, box):
        self.eye_tracker.reset(BoundingBox(box.x1, box.y1, box.x2, box.y2))
        self.eye_tracker_active = True

    def _copy_bbox(self, box: BoundingBox, dst: SharedBox) -> bool:
        area = self.eye_detect_area
        x1 = max(area.x1, min(int(box.x1), area.x2))
        y1 = max(area.y1, min(int(box.y1), area.y2))
        x2 = max(area.x1, min(int(box.x2), area.x2))
        y2 = max(area.y1, min(int(box.y2), area.y2))
        if (x2 - x1) < MIN_SEARCH_BOX or (y2 - y1) < MIN_SEARCH_BOX:
            return False
        dst.x1, dst.y1, dst.x2, dst.y2 = x1, y1, x2, y2
        return True

    def _fuse(self, yolo_point, dark_point):
        if yolo_point is not None and dark_point is not None:
            yolo_weight = 2.0
            total = yolo_weight + 1.0
            return Point(
                (yolo_weight * yolo_point.x + dark_point.x) / total,
                (yolo_weight * yolo_point.y + dark_point.y) / total,
            )
        return yolo_point if yolo_point is not None else dark_point

    def _update_dark_area(self, box, width: int, height: int, scale: float = 2.0) -> bool:
        if not self._box_is_reasonable(box):
            return False
        bw = box.x2 - box.x1
        bh = box.y2 - box.y1
        cx = (box.x1 + box.x2) / 2.0
        cy = (box.y1 + box.y2) / 2.0
        nw = bw * scale
        nh = bh * scale
        x1 = max(0, int(cx - nw / 2.0))
        y1 = max(0, int(cy - nh / 2.0))
        x2 = min(width, int(cx + nw / 2.0))
        y2 = min(height, int(cy + nh / 2.0))
        if (x2 - x1) < MIN_SEARCH_BOX or (y2 - y1) < MIN_SEARCH_BOX:
            return False
        self.dark_detect_area.x1 = x1
        self.dark_detect_area.y1 = y1
        self.dark_detect_area.x2 = x2
        self.dark_detect_area.y2 = y2
        return True

    def _box_is_reasonable(self, box) -> bool:
        if box is None:
            return False
        if hasattr(box, 'is_valid') and callable(box.is_valid):
            if not box.is_valid():
                return False
        return (box.x2 - box.x1) >= MIN_SEARCH_BOX and (box.y2 - box.y1) >= MIN_SEARCH_BOX

    def _set_search_area(self, area: SharedBox, height: int, width: int):
        roi = self.roi
        if roi.is_valid() and (roi.x2 - roi.x1) >= MIN_SEARCH_BOX and (roi.y2 - roi.y1) >= MIN_SEARCH_BOX:
            area.x1, area.y1 = max(0, roi.x1), max(0, roi.y1)
            area.x2, area.y2 = min(width, roi.x2), min(height, roi.y2)
        else:
            area.x1, area.y1, area.x2, area.y2 = 0, 0, width, height

    def _copy_box(self, src: SharedBox, dst: SharedBox):
        dst.x1, dst.y1 = src.x1, src.y1
        dst.x2, dst.y2 = src.x2, src.y2
