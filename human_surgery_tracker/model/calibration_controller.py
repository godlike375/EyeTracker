from time import sleep
from typing import Callable, List, Optional

import cv2
import numpy as np

from tracker.camera import VideoAdapter
from tracker.single_object_tracker import SingleObjectTracker
from tracker.utils.contour_tracker import ContourTracker
from tracker.utils.coordinates import BoundingBox, Point
from tracker.utils.logger import logger

from .area_controller import AreaController
from .interfaces import Notifier
from .laser_controller import LaserController

CONTOUR_DOWNSCALE = 0.5
START_THRESHOLD = 243
MIN_THRESHOLD = 96
THRESHOLD_STEP = 3
DELAY_SEC = 1 / 30
SETTLE_SEC = 0.3
TRACKER_WARMUP_SEC = 0.5
BLOB_KERNEL_SIZE = 13


class CalibrationController:
    def __init__(self,
                 laser: LaserController,
                 area: AreaController,
                 video_adapter: VideoAdapter,
                 notifier: Optional[Notifier] = None,
                 downscale_factor: float = 0.5,
                 target_fps: int = 60,
                 spot_provider: Optional[Callable[[], Optional[Point]]] = None,
                 on_corner: Optional[Callable[[int, Point], None]] = None):
        self.laser = laser
        self.area = area
        self.video_adapter = video_adapter
        self.notifier = notifier
        self.downscale_factor = downscale_factor
        self.target_fps = target_fps
        self.spot_provider = spot_provider
        self.on_corner = on_corner
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def find_laser_spot_roi(self) -> Optional[BoundingBox]:
        current = self.laser.current_position
        farthest = max(self.laser.laser_borders, key=lambda p: p.calc_distance(current))
        self.laser.set_new_position(farthest)

        recorded_frames = []
        while not self.laser.controller_is_ready():
            if self._cancel:
                return None
            frame = self.video_adapter.get_copy_video_frame()
            frame = cv2.resize(frame, (int(frame.shape[1] * CONTOUR_DOWNSCALE),
                                       int(frame.shape[0] * CONTOUR_DOWNSCALE)))
            frame = cv2.medianBlur(frame, 3)
            recorded_frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            sleep(DELAY_SEC)

        if not recorded_frames:
            return None

        start_threshold = START_THRESHOLD
        step = THRESHOLD_STEP
        sticked_objects = None
        while start_threshold > MIN_THRESHOLD:
            if self._cancel:
                return None
            start_threshold, step, extracted = self._extract_contours(
                start_threshold, step, recorded_frames)
            tracker = ContourTracker()
            objects = tracker.track_moving_objects(extracted)
            tracker.calculate_objects_characteristics(objects)
            objects = tracker.filter_objects(objects)
            if objects:
                for obj_id in objects:
                    objects[obj_id].trajectory = tracker.translate_trajectories_relative(
                        objects[obj_id].trajectory)
                sticked_objects = tracker.stick_close_objects(objects)
                if len(sticked_objects) > 1:
                    start_threshold += step // 2
                    continue
                break
            start_threshold -= step

        if not sticked_objects:
            return None

        ids = list(sticked_objects.keys())
        ids.extend(list(sticked_objects[ids[0]]))
        final_contours = [objects[obj_id] for obj_id in ids]
        min_left = min(o.last_box[0].x for o in final_contours) / CONTOUR_DOWNSCALE
        min_top = min(o.last_box[0].y for o in final_contours) / CONTOUR_DOWNSCALE
        max_right = max(o.last_box[1].x for o in final_contours) / CONTOUR_DOWNSCALE
        max_bottom = max(o.last_box[1].y for o in final_contours) / CONTOUR_DOWNSCALE
        return BoundingBox(int(min_left), int(min_top), int(max_right), int(max_bottom))

    def _extract_contours(self, start_threshold, step, frames):
        extracted = []
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (BLOB_KERNEL_SIZE, BLOB_KERNEL_SIZE))
        for frame in frames:
            mask = cv2.threshold(np.copy(frame), start_threshold, 255, cv2.THRESH_BINARY)[1]
            if mask.max() == 0:
                start_threshold -= step
                break
            mask = cv2.erode(mask, kernel, iterations=1)
            mask = cv2.dilate(mask, kernel, iterations=1)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            extracted.append(contours)
        return start_threshold, step, extracted

    def calibrate(self,
                  seed_roi: Optional[BoundingBox] = None,
                  on_progress: Optional[Callable[[int], None]] = None) -> bool:
        self._cancel = False
        if not self.laser.is_initialized:
            self._notify_error('Лазер не подключён, калибровка невозможна')
            return False

        def progress(value):
            if on_progress:
                on_progress(value)

        if self.spot_provider is not None:
            return self._calibrate_with_known_spot(progress)

        if seed_roi is None:
            progress(5)
            seed_roi = self.find_laser_spot_roi()
            if seed_roi is None:
                self._notify_error('Не удалось автоматически определить позицию лазера')
                return False

        tracker = SingleObjectTracker(
            seed_roi, self.video_adapter,
            target_fps=self.target_fps,
            downscale_factor=self.downscale_factor,
        )
        tracker.start_process()
        try:
            sleep(TRACKER_WARMUP_SEC)
            if self._cancel or not tracker.is_tracking:
                return False

            screen_points: List[Point] = []
            for index, border in enumerate(self.laser.laser_borders):
                if self._cancel:
                    return False
                if not self._wait_controller_ready():
                    return False
                self.laser.set_new_position(border)
                if not self._wait_controller_ready():
                    return False
                sleep(SETTLE_SEC)
                screen_points.append(Point(int(tracker.center.x), int(tracker.center.y)))
                if self.on_corner:
                    self.on_corner(index, screen_points[-1])
                progress(5 + int((index + 1) / len(self.laser.laser_borders) * 90))

            if self._cancel:
                return False

            self.area.set_area(screen_points, self.laser.laser_borders)
            logger.debug(f'coordinate system calibrated with {[p.to_tuple() for p in screen_points]}')
            self.notify('Калибровка координатной системы успешно завершена')
            progress(100)
            return True
        finally:
            tracker.stop_process()
            self.laser.center_laser()

    def _calibrate_with_known_spot(self, progress: Callable[[int], None]) -> bool:
        screen_points: List[Point] = []
        for index, border in enumerate(self.laser.laser_borders):
            if self._cancel:
                return False
            if not self._wait_controller_ready():
                return False
            self.laser.set_new_position(border)
            if not self._wait_controller_ready():
                return False
            sleep(SETTLE_SEC)
            point = self.spot_provider()
            if point is None:
                self._notify_error('Не удалось определить позицию виртуального лазера')
                return False
            screen_points.append(Point(int(point.x), int(point.y)))
            if self.on_corner:
                self.on_corner(index, screen_points[-1])
            progress(5 + int((index + 1) / len(self.laser.laser_borders) * 90))

        if self._cancel:
            return False

        self.area.set_area(screen_points, self.laser.laser_borders)
        logger.debug(f'coordinate system calibrated (mock) with {[p.to_tuple() for p in screen_points]}')
        self.notify('Калибровка координатной системы успешно завершена')
        progress(100)
        self.laser.center_laser()
        return True

    def _wait_controller_ready(self) -> bool:
        while not self.laser.controller_is_ready():
            if self._cancel:
                return False
            sleep(DELAY_SEC)
        return True

    def _notify_error(self, message: str):
        logger.error(message)
        if self.notifier:
            self.notifier.show_error(message)

    def notify(self, message: str):
        if self.notifier:
            self.notifier.notify(message)
