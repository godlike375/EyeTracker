from multiprocessing import Process

from tracker.camera import VideoAdapter
from tracker.utils.coordinates import BoundingBox, Point, calc_center
from tracker.utils.correlation_tracker import CorrelationBoxTracker
from tracker.utils.fps import FPSCounter, FPSLimiter
from tracker.utils.logger import logger
from tracker.utils.shared_objects import SharedBox, SharedFlag, SharedPoint

MIN_CONFIDENCE = 4.65
DEFAULT_DOWNSCALE_FACTOR = 0.5
DEFAULT_MEAN_COORDINATES_FRAME_COUNT = 4


class SingleObjectTracker:
    def __init__(self,
                 coordinates: BoundingBox,
                 video_adapter: VideoAdapter,
                 target_fps: int = 60,
                 downscale_factor: float = DEFAULT_DOWNSCALE_FACTOR,
                 mean_count: int = DEFAULT_MEAN_COORDINATES_FRAME_COUNT,
                 noise_threshold: float = 0.0,
                 min_confidence: float = MIN_CONFIDENCE):
        self.video_adapter = video_adapter.send_to_process()
        self.initial_box = coordinates
        self.target_fps = int(target_fps)
        self.downscale = float(downscale_factor)
        self.mean_count = int(mean_count)
        self.noise_threshold = float(noise_threshold)
        self.min_confidence = float(min_confidence)

        self.box = SharedBox('i', 0)
        self.center = SharedPoint('i', 0)
        self.is_lost = SharedFlag(False)
        self._stop = SharedFlag(False)
        self.process = None

    @property
    def is_tracking(self) -> bool:
        return self.process is not None and self.process.is_alive()

    @classmethod
    def from_points(cls, left_top: Point, right_bottom: Point, video_adapter: VideoAdapter, **kwargs):
        box = BoundingBox(int(left_top.x), int(left_top.y),
                          int(right_bottom.x), int(right_bottom.y))
        return cls(box, video_adapter, **kwargs)

    @classmethod
    def from_roi(cls, roi, video_adapter: VideoAdapter, **kwargs):
        left, top, right, bottom = roi
        return cls(BoundingBox(int(left), int(top), int(right), int(bottom)),
                   video_adapter, **kwargs)

    @property
    def position(self) -> Point:
        return Point(self.center.x, self.center.y)

    @property
    def tracked_box(self) -> BoundingBox:
        return BoundingBox(self.box.x1, self.box.y1, self.box.x2, self.box.y2)

    def start_process(self):
        if self.is_tracking:
            return self.process
        self._stop.set(False)
        self.is_lost.set(False)
        self._write_box(self.initial_box)
        self._write_center(calc_center(
            Point(self.initial_box.x1, self.initial_box.y1),
            Point(self.initial_box.x2, self.initial_box.y2),
        ))
        self.process = Process(target=self._mainloop, name="SingleObjectTracker", daemon=True)
        self.process.start()
        logger.debug('single object tracker started')
        return self.process

    def stop_process(self):
        if self.process is None:
            return
        self._stop.set(True)
        self.process.join(timeout=2)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=1)
            if self.process.is_alive():
                self.process.kill()
        self.process = None
        logger.debug('single object tracker stopped')

    def _mainloop(self):
        self.video_adapter.setup_video_frame()
        fps = FPSLimiter(self.target_fps)
        fps_counter = FPSCounter(1.5)
        core = CorrelationBoxTracker(
            downscale_factor=self.downscale,
            mean_count=self.mean_count,
            noise_threshold=self.noise_threshold,
            min_confidence=self.min_confidence,
        )
        core.reset(self.initial_box)

        while not self._stop:
            if not fps.able_to_execute():
                fps.throttle()

            frame = self.video_adapter.get_copy_video_frame()
            box, center, lost = core.update(frame)
            self.is_lost.set(lost)
            self._write_box(box)
            self._write_center(center)

            fps_counter.count_frame()
            if fps_counter.able_to_calculate():
                logger.debug(f'single object tracker fps: {fps_counter.calculate()}')

    def _write_box(self, box: BoundingBox):
        self.box.x1, self.box.y1 = box.x1, box.y1
        self.box.x2, self.box.y2 = box.x2, box.y2

    def _write_center(self, center: Point):
        self.center.x, self.center.y = int(center.x), int(center.y)
