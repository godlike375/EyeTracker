import cv2
import numpy as np

from tracker.utils.coordinates import Point

SPLIT_PARTS = 4
# другие значения не работают с 90 градусов поворотом при разрешениях кроме 640

FONT_SCALE = 0.8


COLOR_CAUTION = (0, 0, 255)
THICKNESS = 2
CURRENT_COLOR = (150, 240, 40)

RESOLUTIONS = {1280: 720, 800: 600, 640: 480}
DOWNSCALED_WIDTH = 640

DEGREE_TO_CV2_MAP = {90: cv2.ROTATE_90_CLOCKWISE,
                     180: cv2.ROTATE_180,
                     270: cv2.ROTATE_90_COUNTERCLOCKWISE}


def draw_rectangle(frame, left_top: Point, right_bottom: Point):
    left_top = left_top.to_int()
    right_bottom = right_bottom.to_int()
    if left_top and right_bottom and left_top != right_bottom and left_top != Point(0, 0):
        return cv2.rectangle(frame, (*left_top,), (*right_bottom,), CURRENT_COLOR, THICKNESS)
    return frame

def draw_circle(frame, center: Point):
    center = center.to_int()
    return cv2.circle(frame, (*center,), radius=THICKNESS, color=CURRENT_COLOR, thickness=THICKNESS)

def draw_line(frame, start: Point, end: Point):
    start = start.to_int()
    end = end.to_int()
    return cv2.line(frame, (*start,), (*end,), color=CURRENT_COLOR, thickness=THICKNESS)

def draw_text(frame, text: str, coords: Point, font_scale: float = FONT_SCALE):
    font = cv2.FONT_HERSHEY_SIMPLEX
    return cv2.putText(frame, text, (coords.x, coords.y), font,
                       font_scale, CURRENT_COLOR, THICKNESS, cv2.LINE_AA)

def resize_frame_relative(frame, percent):
    return cv2.resize(frame, (0, 0), fx=percent, fy=percent, interpolation=cv2.INTER_AREA)

def resize_frame_absolute(frame, new_height, new_width):
    return cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)

def resize_to_minimum(frame):
    frame_width = frame.shape[0]
    frame_height = frame.shape[1]
    if frame_height == DOWNSCALED_WIDTH or frame_width == DOWNSCALED_WIDTH:
        return frame
    reversed = frame_height < frame_width
    down_width = RESOLUTIONS[DOWNSCALED_WIDTH]
    if reversed:
        return resize_frame_absolute(frame, DOWNSCALED_WIDTH, down_width)
    return resize_frame_absolute(frame, down_width, DOWNSCALED_WIDTH)

def frames_are_same(one: np.ndarray, another: np.ndarray, same_threshold: float):
    if one is None or another is None:
        return False
    if one.shape != another.shape:
        return False
    return all(i.mean() > same_threshold for i in np.split((one == another), SPLIT_PARTS))


def rotate_frame(frame: np.ndarray, degree: int):
    if degree:
        return cv2.rotate(frame, DEGREE_TO_CV2_MAP[degree])
    else:
        return frame
