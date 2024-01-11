from threading import Thread

from winsound import PlaySound, SND_PURGE, SND_FILENAME

from eye_tracker.common.settings import ASSETS_FOLDER
from eye_tracker.common.coordinates import Point, get_translation_maxtix, translate_coordinates
from eye_tracker.common.logger import logger
from eye_tracker.common.settings import get_repo_path
from eye_tracker.model.selector import AreaSelector
from eye_tracker.view.drawing import Processor

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
        self._translation_matrix = get_translation_maxtix(area.points, laser_borders)

        Processor.load_color()
        logger.debug(f'set area {area.points}')

    def point_is_out_of_area(self, point: Point, beep_sound_allowed=False) -> bool:
        # https://docs.opencv.org/4.x/da/d54/group__imgproc__transform.html#gaf73673a7e8e18ec6963e3774e6a94b87
        translated = translate_coordinates(self._translation_matrix, point)
        out_of_area = translated.x < self._min_xy.x or translated.x > self._max_xy.x \
            or translated.y < self._min_xy.y or translated.y > self._max_xy.y
        if beep_sound_allowed:
            self.beep(out_of_area)
        return out_of_area

    def beep(self, out_of_area):
        if out_of_area and not self._beeped:
            sound_path = str(get_repo_path(bundled=True) / ASSETS_FOLDER / SOUND_NAME)
            Thread(target=PlaySound, args=(sound_path, SND_FILENAME | SND_PURGE)).start()
            self._beeped = True
            Processor.CURRENT_COLOR = Processor.COLOR_CAUTION
        if not out_of_area:
            Processor.load_color()
            self._beeped = False

    def calc_laser_coords(self, object_center: Point) -> Point:
        translated_center = translate_coordinates(self._translation_matrix, object_center)
        return translated_center
