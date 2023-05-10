import cv2
import numpy as np
from PIL import Image

from common.coordinates import Point
from common.logger import logger
from common.settings import settings, private_settings, RESOLUTIONS, DOWNSCALED_WIDTH

SPLIT_PARTS = 4
# другие значения не работают с 90 градусов поворотом при разрешениях кроме 640


class Processor:
    # white
    COLOR_NORMAL = (private_settings.PAINT_COLOR_R, private_settings.PAINT_COLOR_G, private_settings.PAINT_COLOR_B)
    COLOR_CAUTION = (0, 0, 255)
    THICKNESS = 2
    CURRENT_COLOR = COLOR_NORMAL
    FONT_SCALE = 0.8

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
        return cv2.circle(frame, (*center,), radius=cls.THICKNESS, color=cls.CURRENT_COLOR, thickness=cls.THICKNESS)

    @classmethod
    def draw_line(cls, frame, start: Point, end: Point):
        start = start.to_int()
        end = end.to_int()
        return cv2.line(frame, (*start,), (*end,), color=cls.CURRENT_COLOR, thickness=cls.THICKNESS)

    @classmethod
    def draw_text(cls, frame, text: str, coords: Point):
        font = cv2.FONT_HERSHEY_SIMPLEX
        return cv2.putText(frame, text, (coords.x, coords.y), font,
                           cls.FONT_SCALE, Processor.CURRENT_COLOR, cls.THICKNESS, cv2.LINE_AA)

    @staticmethod
    def resize_frame_relative(frame, percent):
        width = int(frame.shape[1] * percent)
        height = int(frame.shape[0] * percent)
        return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

    def resize_frame_absolute(frame, new_height, new_width):
        return cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)

    @classmethod
    def resize_to_minimum(cls, frame):
        frame_width = frame.shape[0]
        frame_height = frame.shape[1]
        if frame_height == DOWNSCALED_WIDTH or frame_width == DOWNSCALED_WIDTH:
            return frame
        reversed = frame_height < frame_width
        down_width = RESOLUTIONS[DOWNSCALED_WIDTH]
        if reversed:
            return cls.resize_frame_absolute(frame, DOWNSCALED_WIDTH, down_width)
        return cls.resize_frame_absolute(frame, down_width, DOWNSCALED_WIDTH)

    @classmethod
    def frames_are_same(cls, one, another):
        if one is None or another is None:
            return False
        if one.shape != another.shape:
            return False
        one = cls.resize_frame_relative(one, settings.DOWNSCALE_FACTOR)
        another = cls.resize_frame_relative(another, settings.DOWNSCALE_FACTOR)
        return all(i.mean() > settings.SAME_FRAMES_THRESHOLD for i in np.split((one == another), SPLIT_PARTS))

    @classmethod
    def load_color(cls):
        # TODO: возможно еще добавить выбор цвета предупреждения
        ps = private_settings
        color = (ps.PAINT_COLOR_B, ps.PAINT_COLOR_G, ps.PAINT_COLOR_R)
        cls.COLOR_NORMAL = color
        cls.CURRENT_COLOR = color
