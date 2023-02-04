from abc import ABC
from typing import List

import cv2
from PIL import Image

from common.coordinates import Point
from common.logger import logger


class Drawable(ABC):
    def draw_on_frame(self, frame):
        pass


class Processor:
    # white
    COLOR_WHITE = (255, 255, 255)
    COLOR_RED = (0, 0, 255)
    THICKNESS = 2
    CURRENT_COLOR = COLOR_WHITE

    @staticmethod
    def frame_to_image(frame):
        if frame is None:
            logger.fatal('Frame is None type')
            raise Exception('Не удалось обработать кадр')
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb = Image.fromarray(rgb)
        return rgb

    @classmethod
    def draw_rectangle(cls, frame, left_top: Point, right_bottom: Point):
        left_top = left_top.to_int()
        right_bottom = right_bottom.to_int()
        # TODO: возможно понадобится более серьезная защита типа проверки на NAN и тд
        if left_top and right_bottom and left_top != right_bottom and left_top != Point(0, 0):
            return cv2.rectangle(frame, (*left_top,), (*right_bottom,), cls.CURRENT_COLOR, cls.THICKNESS)
        return frame

    @classmethod
    def draw_circle(cls, frame, center: Point):
        center = center.to_int()
        return cv2.circle(frame, (*center,), radius=cls.THICKNESS, color=cls.COLOR_WHITE, thickness=cls.THICKNESS)

    @classmethod
    def draw_line(cls, frame, start: Point, end: Point):
        start = start.to_int()
        end = end.to_int()
        return cv2.line(frame, (*start,), (*end,), color=cls.COLOR_WHITE, thickness=cls.THICKNESS)

    @classmethod
    def draw_active_objects(cls, frame, active_objects: List[Drawable]):  # RectBased list
        for obj in active_objects:
            frame = obj.draw_on_frame(frame)
        return frame
