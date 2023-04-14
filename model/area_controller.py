from threading import Thread
from winsound import PlaySound, SND_PURGE, SND_FILENAME

import cv2
import numpy as np

from common.coordinates import Point
from common.logger import logger
from common.settings import get_repo_path
from model.selector import AreaSelector
from view import view_output
from view.drawing import Processor

SOUND_NAME = 'alert.wav'


class AreaController:

    def __init__(self, min_xy, max_xy):
        # max resolution in abstract distance units
        self._resolution_xy = abs(min_xy - max_xy)
        self._max_xy = Point(0, 0)
        self._dpi_xy = Point(0, 0)
        self._translation_matrix = None
        self._is_set = False
        self._beeped = False
        self._automate_selected = False

    @staticmethod
    def calc_center(left_top: Point, right_bottom: Point) -> Point:
        return Point(int((left_top.x + right_bottom.x) / 2), int((left_top.y + right_bottom.y) / 2))

    def set_area(self, area: AreaSelector, laser_points=None):
        points = area.points
        tl, tr, br, bl = points
        if laser_points is not None:
            transformed_points = [(*p,) for p in laser_points]
            transformed_points_array = np.array(transformed_points,
                                                dtype="float32")
        else:
        # https://theailearner.com/tag/cv2-getperspectivetransform/
            bottom_width = np.sqrt(((br.x - bl.x) ** 2) + ((br.y - bl.y) ** 2))
            top_width = np.sqrt(((tr.x - tl.x) ** 2) + ((tr.y - tl.y) ** 2))
            max_width = max(int(bottom_width), int(top_width))

            right_height = np.sqrt(((tr.x - br.x) ** 2) + ((tr.y - br.y) ** 2))
            left_height = np.sqrt(((tl.x - bl.x) ** 2) + ((tl.y - bl.y) ** 2))
            max_height = max(int(right_height), int(left_height))
            max_size = max(max_height, max_width)
            transformed_points_array = np.array([[0, 0], [max_size, 0], [max_size, max_size], [0, max_size]],
                                                dtype="float32")
            self._max_xy = Point(max_size, max_size)
            self.center = Point(max_size / 2, max_size / 2)
            try:
                self._dpi_xy = Point(self._resolution_xy / self._max_xy.x, self._resolution_xy / self._max_xy.y)
            except ZeroDivisionError:
                # TODO: проверить, остался ли этот кейс
                view_output.show_message('Область не может быть пустой', 'Ошибка')
                return

        points_array = np.array([(*pt,) for pt in points], dtype="float32")

        self._translation_matrix = cv2.getPerspectiveTransform(points_array, transformed_points_array)



        self._is_set = True
        if laser_points is not None:
            self._automate_selected = True
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
        if self._automate_selected:
            # TODO: доделать логику или переделать
            return False
        if not self._is_set:
            self._beeped = False
            return False
        # https://docs.opencv.org/4.x/da/d54/group__imgproc__transform.html#gaf73673a7e8e18ec6963e3774e6a94b87
        translated = self.translate_coordinates(point)
        out_of_area = translated.x < 0 or translated.x > self._max_xy.x \
            or translated.y < 0 or translated.y > self._max_xy.y
        if beep_sound_allowed:
            self.beep(out_of_area)
        return out_of_area

    def beep(self, out_of_area):
        if out_of_area and not self._beeped:
            sound_path = str(get_repo_path(bundled=True) / SOUND_NAME)
            Thread(target=PlaySound, args=(sound_path, SND_FILENAME | SND_PURGE)).start()
            self._beeped = True
            Processor.CURRENT_COLOR = Processor.COLOR_RED
        if not out_of_area:
            Processor.CURRENT_COLOR = Processor.COLOR_GREEN
            self._beeped = False

    def calc_laser_coords(self, object_center: Point) -> Point:
        translated_center = self.translate_coordinates(object_center)
        if self._automate_selected:
            return translated_center
        relative = translated_center - self.center
        relative *= self._dpi_xy
        return relative.to_int()
