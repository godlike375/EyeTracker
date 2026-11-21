import cv2
import dlib
import numpy

from tracker.utils.coordinates import BoundingBox, Point, calc_center
from tracker.utils.denoiser import Denoiser

MIN_CONFIDENCE = 4.65
DEFAULT_DOWNSCALE_FACTOR = 0.5
DEFAULT_MEAN_COORDINATES_FRAME_COUNT = 4


class CorrelationBoxTracker:
    """Frame-by-frame correlation (dlib) tracker for a single bounding box.

    Process-agnostic: the caller feeds frames and gets the tracked box/center.
    Reused both by the standalone ``SingleObjectTracker`` process and inline
    inside the pupil pipeline.
    """

    def __init__(self, downscale_factor: float = DEFAULT_DOWNSCALE_FACTOR,
                 mean_count: int = DEFAULT_MEAN_COORDINATES_FRAME_COUNT,
                 noise_threshold: float = 0.0,
                 min_confidence: float = MIN_CONFIDENCE):
        self.downscale = float(downscale_factor)
        self.mean_count = int(mean_count)
        self.noise_threshold = float(noise_threshold)
        self.min_confidence = float(min_confidence)
        self._tracker = None
        self._box = None
        self._center = None
        self._denoisers = []
        self._started = False
        self._last_center = None

    @property
    def box(self) -> BoundingBox:
        return self._box

    @property
    def center(self) -> Point:
        return self._center

    def reset(self, box: BoundingBox):
        self._tracker = dlib.correlation_tracker()
        self._box = box
        self._center = calc_center(Point(box.x1, box.y1), Point(box.x2, box.y2))
        self._denoisers = [Denoiser(coord, self.mean_count)
                           for coord in (box.x1, box.y1, box.x2, box.y2)]
        self._started = False
        self._last_center = None

    def update(self, frame: numpy.ndarray):
        scaled = self._downscale(frame)
        if not self._started:
            self._start_track(scaled, self._scale_box(self._box))
            self._started = True

        confidence = self._tracker.update(scaled)
        lost = confidence < self.min_confidence

        tracked = self._to_original_box(self._tracker.get_position())
        for denoiser, coord in zip(self._denoisers, (tracked.x1, tracked.y1, tracked.x2, tracked.y2)):
            denoiser.add(coord)

        self._box = BoundingBox(
            int(self._denoisers[0].get()), int(self._denoisers[1].get()),
            int(self._denoisers[2].get()), int(self._denoisers[3].get()),
        )
        center = calc_center(Point(self._box.x1, self._box.y1), Point(self._box.x2, self._box.y2))
        if self._last_center is None or center.calc_distance(self._last_center) >= self.noise_threshold:
            self._last_center = center
            self._center = center
        return self._box, self._center, lost

    def _start_track(self, scaled, box: BoundingBox):
        height, width = scaled.shape[:2]
        left = min(max(int(box.x1), 0), width - 1)
        top = min(max(int(box.y1), 0), height - 1)
        right = min(max(int(box.x2), left + 1), width - 1)
        bottom = min(max(int(box.y2), top + 1), height - 1)
        self._tracker.start_track(scaled, dlib.rectangle(left, top, right, bottom))

    def _downscale(self, frame: numpy.ndarray) -> numpy.ndarray:
        if self.downscale >= 1.0:
            return frame
        height, width = frame.shape[:2]
        return cv2.resize(frame, (max(int(width * self.downscale), 1),
                                  max(int(height * self.downscale), 1)))

    def _scale_box(self, box: BoundingBox) -> BoundingBox:
        d = self.downscale
        return BoundingBox(int(box.x1 * d), int(box.y1 * d),
                           int(box.x2 * d), int(box.y2 * d))

    def _to_original_box(self, rect) -> BoundingBox:
        d = self.downscale
        return BoundingBox(int(rect.left() / d), int(rect.top() / d),
                           int(rect.right() / d), int(rect.bottom() / d))
