from threading import Thread
from winsound import PlaySound, SND_PURGE, SND_FILENAME

import cv2
import numpy as np

from common.coordinates import Point
from common.logger import logger
from common.settings import get_repo_path
from model.selector import AreaSelector
from view.drawing import Processor

SOUND_NAME = 'alert.wav'


class AreaController:

    def __init__(self, min_xy, max_xy):
        # max resolution in abstract distance units
        self._resolution_xy = abs(min_xy - max_xy)
        self._max_xy = Point(max_xy, max_xy)
        self._min_xy = Point(min_xy, min_xy)
        self._translation_matrix = None
        self._beeped = False

    def set_area(self, area: AreaSelector, laser_borders=None):
        points = area.points
        transformed_points = [(*p,) for p in laser_borders]
        transformed_points_array = np.array(transformed_points, dtype="float32")
        # https://theailearner.com/tag/cv2-getperspectivetransform/

        points_array = np.array([(*pt,) for pt in points], dtype="float32")

        self._translation_matrix = cv2.getPerspectiveTransform(points_array, transformed_points_array)

        Processor.load_color()
        logger.debug(f'set area {points}')

    def translate_coordinates(self, point: Point):
        m = self._translation_matrix
        x = point.x
        y = point.y
        common_denominator = (m[2, 0] * x + m[2, 1] * y + m[2, 2])
        X = (m[0, 0] * x + m[0, 1] * y + m[0, 2]) / common_denominator
        Y = (m[1, 0] * x + m[1, 1] * y + m[1, 2]) / common_denominator
        return Point(int(X), int(Y))

    def point_is_out_of_area(self, point: Point, beep_sound_allowed=False) -> bool:
        # https://docs.opencv.org/4.x/da/d54/group__imgproc__transform.html#gaf73673a7e8e18ec6963e3774e6a94b87
        translated = self.translate_coordinates(point)
        out_of_area = translated.x < self._min_xy.x or translated.x > self._max_xy.x \
            or translated.y < self._min_xy.y or translated.y > self._max_xy.y
        if beep_sound_allowed:
            self.beep(out_of_area)
        return out_of_area

    def beep(self, out_of_area):
        if out_of_area and not self._beeped:
            sound_path = str(get_repo_path(bundled=True) / SOUND_NAME)
            Thread(target=PlaySound, args=(sound_path, SND_FILENAME | SND_PURGE)).start()
            self._beeped = True
            Processor.CURRENT_COLOR = Processor.COLOR_CAUTION
        if not out_of_area:
            Processor.load_color()
            self._beeped = False

    def calc_laser_coords(self, object_center: Point) -> Point:
        translated_center = self.translate_coordinates(object_center)
        return translated_center
