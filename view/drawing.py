from abc import ABC
from typing import List

import cv2
from PIL import Image

from common.coordinates import Point


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
        # TODO: проверить, почему пустые кадры прилетают
        if not len(frame):
            raise Exception('Кадр с вебкамеры оказался пустым')
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb = Image.fromarray(rgb)
        return rgb

    @classmethod
    def _draw_rectangle(cls, frame, left_top: Point, right_bottom: Point):
        return cv2.rectangle(frame, (*left_top,), (*right_bottom,), cls.CURRENT_COLOR, cls.THICKNESS)

    @classmethod
    def draw_circle(cls, frame, center: Point):
        return cv2.circle(frame, (*center,), radius=cls.THICKNESS, color=cls.COLOR_WHITE, thickness=cls.THICKNESS)

    @classmethod
    def draw_line(cls, frame, start: Point, end: Point):
        return cv2.line(frame, (*start,), (*end,), color=cls.COLOR_WHITE, thickness=cls.THICKNESS)

    @classmethod
    def draw_active_objects(cls, frame, active_objects: List[Drawable]):  # RectBased list
        for obj in active_objects:
            # TODO: реализовать отрисовку собственными силами Selector
            frame = obj.draw_on_frame(frame)
            # frame = cls._draw_rectangle(frame, obj.left_top, obj.right_bottom)
        return frame
