import cv2
import numpy as np

from tracker.utils.shared_objects import SharedPoint, SharedBox

COLOR_PUPIL_VALID = (0, 255, 0)
COLOR_PUPIL_INVALID = (0, 0, 255)
COLOR_EYE_BOX = (255, 128, 0)
COLOR_ROI_SELECTION = (255, 0, 255)
COLOR_LASER = (0, 255, 255)
COLOR_LASER_VIRTUAL = (0, 165, 255)
COLOR_CALIBRATION = (255, 255, 0)
COLOR_BORDER_WARNING = (0, 0, 255)
COLOR_TEXT = (255, 255, 255)
COLOR_CROSSHAIR = (128, 128, 128)

POINTS_ORIENTATION = ['TL', 'TR', 'BR', 'BL']

THICKNESS_THIN = 1
THICKNESS_NORMAL = 2
THICKNESS_THICK = 3

FONT_SCALE_SMALL = 0.4
FONT_SCALE_NORMAL = 0.5
FONT_SCALE_LARGE = 0.7


def draw_pupil(frame: np.ndarray, pupil: SharedPoint) -> np.ndarray:
    if not pupil.is_valid:
        return frame
    x, y = int(pupil.x), int(pupil.y)
    cv2.circle(frame, (x, y), 6, COLOR_PUPIL_VALID, -1)
    cv2.circle(frame, (x, y), 7, (255, 255, 255), THICKNESS_THIN)
    return frame


def draw_eye_box(frame: np.ndarray, eye_box: SharedBox) -> np.ndarray:
    if not eye_box.is_valid:
        return frame
    lt = (int(eye_box.left_top.x), int(eye_box.left_top.y))
    rb = (int(eye_box.right_bottom.x), int(eye_box.right_bottom.y))
    cv2.rectangle(frame, lt, rb, COLOR_EYE_BOX, THICKNESS_NORMAL)
    return frame


def draw_roi_selection(frame: np.ndarray, start: tuple, end: tuple) -> np.ndarray:
    cv2.rectangle(frame, start, end, COLOR_ROI_SELECTION, THICKNESS_NORMAL)
    cv2.drawMarker(frame, start, COLOR_ROI_SELECTION, cv2.MARKER_CROSS, 10, THICKNESS_THIN)
    cv2.drawMarker(frame, end, COLOR_ROI_SELECTION, cv2.MARKER_CROSS, 10, THICKNESS_THIN)
    return frame


def draw_laser_position(frame: np.ndarray, position: tuple, color=COLOR_LASER) -> np.ndarray:
    cv2.circle(frame, position, 5, color, -1)
    cv2.circle(frame, position, 6, (255, 255, 255), THICKNESS_THIN)
    cv2.drawMarker(frame, position, color, cv2.MARKER_TILTED_CROSS, 12, THICKNESS_NORMAL)
    return frame


def draw_calibration_area(frame: np.ndarray, points: list) -> np.ndarray:
    if len(points) < 2:
        return frame
    for i in range(len(points) - 1):
        cv2.line(frame, points[i], points[i + 1], COLOR_CALIBRATION, THICKNESS_NORMAL)
    if len(points) == 4:
        cv2.line(frame, points[-1], points[0], COLOR_CALIBRATION, THICKNESS_NORMAL)
    for i, pt in enumerate(points):
        cv2.circle(frame, pt, 4, COLOR_CALIBRATION, -1)
        label = POINTS_ORIENTATION[i] if i < len(POINTS_ORIENTATION) else f"CP{i + 1}"
        cv2.putText(frame, label, (pt[0] + 8, pt[1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE_SMALL, COLOR_CALIBRATION, THICKNESS_THIN)
    return frame


def draw_border_warning(frame: np.ndarray, is_near_border: bool) -> np.ndarray:
    if not is_near_border:
        return frame
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w - 1, h - 1), COLOR_BORDER_WARNING, THICKNESS_THICK)
    text = "BORDER WARNING"
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE_LARGE, THICKNESS_NORMAL)
    cv2.putText(frame, text, ((w - tw) // 2, 30), cv2.FONT_HERSHEY_SIMPLEX,
                FONT_SCALE_LARGE, COLOR_BORDER_WARNING, THICKNESS_NORMAL)
    return frame


def draw_crosshair(frame: np.ndarray, position: tuple) -> np.ndarray:
    x, y = position
    cv2.drawMarker(frame, (x, y), COLOR_CROSSHAIR, cv2.MARKER_CROSS, 20, THICKNESS_THIN)
    return frame


def draw_info_text(frame: np.ndarray, lines: list, position: tuple = (10, 20)) -> np.ndarray:
    x, y = position
    for i, line in enumerate(lines):
        cv2.putText(frame, line, (x, y + i * 18), cv2.FONT_HERSHEY_SIMPLEX,
                    FONT_SCALE_SMALL, COLOR_TEXT, THICKNESS_THIN)
    return frame
