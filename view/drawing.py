import cv2
from PIL import Image

from common.coordinates import Point


class Processor:
    # white
    COLOR_WHITE = (255, 255, 255)
    COLOR_RED = (0, 0, 255)
    THICKNESS = 2
    CURRENT_COLOR = COLOR_WHITE

    @staticmethod
    def crop_frame(frame, left_top, right_bottom):
        return frame[left_top.y:right_bottom.y, left_top.x:right_bottom.x]

    @staticmethod
    def frame_to_image(frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb = Image.fromarray(rgb)
        return rgb

    @classmethod
    def _draw_rectangle(cls, frame, left_top: Point, right_bottom: Point):
        return cv2.rectangle(frame, (*left_top,), (*right_bottom,), cls.CURRENT_COLOR, cls.THICKNESS)

    @classmethod
    def draw_boxes(cls, frame, boxes: list):  # RectBased list
        for box in boxes:
            frame = cls._draw_rectangle(frame, box.left_top, box.right_bottom)
        return frame
