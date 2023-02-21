from threading import Thread
from winsound import PlaySound, SND_PURGE, SND_FILENAME

from common.coordinates import Point
from common.logger import logger
from model.selector import TetragonSelector
from view.drawing import Processor
from view.view_model import ViewModel


class AreaController:

    def __init__(self, min_xy, max_xy):
        # max resolution in abstract distance units
        self._resolution_xy = abs(min_xy - max_xy)
        self._max_xy = Point(0, 0)
        self._dpi_xy = Point(0, 0)
        self._M = None
        self._is_set = False
        self._beeped = False

    @staticmethod
    def calc_center(left_top: Point, right_bottom: Point) -> Point:
        return Point(int((left_top.x + right_bottom.x) / 2), int((left_top.y + right_bottom.y) / 2))

    def set_area(self, area: TetragonSelector):
        if area is None:
            self._is_set = False
            return
        import numpy as np
        import cv2
        tl, tr, br, bl = area.points
        # TODO: отрефакторить
        width_a = np.sqrt(((br.x - bl.x) ** 2) + ((br.y - bl.y) ** 2))
        width_b = np.sqrt(((tr.x - tl.x) ** 2) + ((tr.y - tl.y) ** 2))
        max_width = max(int(width_a), int(width_b))

        height_a = np.sqrt(((tr.x - br.x) ** 2) + ((tr.y - br.y) ** 2))
        height_b = np.sqrt(((tl.x - bl.x) ** 2) + ((tl.y - bl.y) ** 2))
        max_height = max(int(height_a), int(height_b))
        max_size = max(max_height, max_width)
        dst = np.array([[0, 0], [max_size, 0], [max_size, max_size], [0, max_size]], dtype="float32")

        tupled = np.array([(*pt,) for pt in area.points], dtype="float32")
        M = cv2.getPerspectiveTransform(tupled, dst)

        self._M = M

        self._max_xy = Point(max_size, max_size)
        try:
            self._dpi_xy = Point(self._resolution_xy / self._max_xy.x, self._resolution_xy / self._max_xy.y)
        except ZeroDivisionError:
            # TODO: проверить, остался ли этот кейс
            ViewModel.show_message('Область не может быть пустой', 'Ошибка')
            return
        self.center = Point(max_size / 2, max_size / 2)
        self._is_set = True
        logger.debug(f'set area {area.points}')

    def translate_coordinates(self, point: Point):
        m = self._M
        x = point.x
        y = point.y
        common_denominator = (m[2, 0] * x + m[2, 1] * y + m[2, 2])
        X = (m[0, 0] * x + m[0, 1] * y + m[0, 2]) / common_denominator
        Y = (m[1, 0] * x + m[1, 1] * y + m[1, 2]) / common_denominator
        return Point(int(X), int(Y))

    def point_is_out_of_area(self, point: Point, beep_sound=False) -> bool:
        if not self._is_set:
            self._beeped = False
            return False
        # https://docs.opencv.org/4.x/da/d54/group__imgproc__transform.html#gaf73673a7e8e18ec6963e3774e6a94b87
        translated = self.translate_coordinates(point)
        out_of_area = translated.x < 0 or translated.x > self._max_xy.x \
            or translated.y < 0 or translated.y > self._max_xy.y
        if not beep_sound:
            return out_of_area

        if out_of_area and not self._beeped:
            Thread(target=PlaySound, args=(r'alert.wav', SND_FILENAME | SND_PURGE)).start()
            self._beeped = True
            Processor.CURRENT_COLOR = Processor.COLOR_RED
        if not out_of_area:
            Processor.CURRENT_COLOR = Processor.COLOR_WHITE
            self._beeped = False
        return out_of_area

    def calc_relative_coords(self, object_center: Point) -> Point:
        relative = object_center - self.center
        relative *= self._dpi_xy
        return relative
