# import _thread
from threading import Thread
from winsound import PlaySound, SND_PURGE, SND_FILENAME

from common.coordinates import Point
from common.logger import logger
from common.settings import Settings, OBJECT, AREA
from common.thread_helpers import ThreadLoopable
from model.area_controller import AreaController
from model.extractor import Extractor
from model.frame_processing import Tracker
from model.move_controller import MoveController
from model.selector import RectSelector, TetragonSelector
from view.drawing import Processor
from view.view_model import ViewModel


class Model(ThreadLoopable):

    def __init__(self, view_model: ViewModel, run_immediately: bool = True, area: tuple = None):
        self._view_model = view_model
        self._extractor = Extractor(Settings.CAMERA_ID)
        self._tracker = Tracker()
        self._area_controller = AreaController(min_xy=-Settings.MAX_RANGE,
                                               max_xy=Settings.MAX_RANGE)
        self._laser_controller = MoveController(serial_off=False)
        self._current_frame = None
        self._active_drawed_objects = dict()  # {name: RectBased}
        self._beeped = False

        if area is not None:
            self.load_selected_area(area)
        FRAME_INTERVAL_SEC = 1 / Settings.FPS_PROCESSED
        super().__init__(self._processing_loop, FRAME_INTERVAL_SEC, run_immediately)

    def load_selected_area(self, area):
        area_selector = TetragonSelector(AREA, self.on_area_selected, area)
        if area_selector.is_empty:
            return
        area_selector._selected = True
        self._active_drawed_objects[AREA] = area_selector
        self.start_drawing_selected(area_selector)
        # TODO: убрать
        self.on_area_selected()

    def get_or_create_selector(self, name):
        selector = self._active_drawed_objects.get(name)
        if selector is None:
            logger.debug(f'creating new selector {name}')
            on_selected = self.on_object_selected if OBJECT in name else self.on_area_selected
            selector = RectSelector(name, on_selected) if OBJECT in name else TetragonSelector(name, on_selected)
            self._active_drawed_objects[name] = selector
        return selector

    def _processing_loop(self):
        try:
            frame = self._current_frame = self._extractor.extract_frame()
            processed_image = self._tracking_and_drawing(frame)
            self._view_model.on_image_ready(processed_image)
        except RuntimeError as re:
            if 'dictionary changed size during iteration' in str(re):
                return
            if 'dictionary keys changed during iteration' in str(re):
                return
            self.show_fatal_exception(re)
        except Exception as e:
            self.show_fatal_exception(e)

    def show_fatal_exception(self, e):
        # TODO: Возможно переместить во ViewModel
        ViewModel.show_message(title='Фатальная ошибка. Работа программы будет продолжена, но может быть с ошибками',
                               message=f'{e}')
        logger.fatal(e)
        # _thread.interrupt_main()

    def _tracking_and_drawing(self, frame):
        if self._tracker.in_progress:
            self._tracking(frame)
        active_objects = self._active_drawed_objects.values()
        processed = Processor.draw_active_objects(frame, active_objects)
        return Processor.frame_to_image(processed)

    def _tracking(self, frame):
        center = self._tracker.get_tracked_position(frame)
        self._move_to_relative_cords(center)

    def _move_to_relative_cords(self, center):
        out_of_area = self._area_controller.point_is_out_of_area(center)
        # TODO: вынести в отдельный класс или функцию, возможно в AreaContoller
        # TODO: пофиксить звук при комбинации пустой зоны объекта и выделения за границей
        if not out_of_area:
            relative_coords = self._area_controller.calc_relative_coords(center)
            self._laser_controller.set_new_position(relative_coords.to_int())
            Processor.CURRENT_COLOR = Processor.COLOR_WHITE
            self._beeped = False
        else:
            if not self._beeped:
                Thread(target=PlaySound, args=(r'alert.wav', SND_FILENAME | SND_PURGE)).start()
                self._beeped = True
            Processor.CURRENT_COLOR = Processor.COLOR_RED

    def calibrate_laser(self):
        logger.debug('laser calibrated')
        self._laser_controller._move_laser(Point(0, 0), command=2)

    def center_laser(self):
        logger.debug('laser centered')
        self._laser_controller._move_laser(Point(0, 0))

    def move_laser(self, x, y):
        logger.debug(f'laser moved to {x, y}')
        self._laser_controller._move_laser(Point(x, y))

    def stop_drawing_selected(self, name):
        if name in self._active_drawed_objects:
            del self._active_drawed_objects[name]

    def start_drawing_selected(self, selector):
        self._active_drawed_objects[selector.name] = selector

    def check_emptiness(self, selector):
        if selector.is_empty:
            logger.warning('selected area is zero in size')
            ViewModel.show_message('Область не может быть пустой или слишком малого размера', 'Ошибка')
            self.stop_drawing_selected(selector.name)
            selector._selected = False

    def on_area_selected(self):
        area = self.get_or_create_selector(AREA)
        self.check_emptiness(area)
        if area.is_selected:
            self._area_controller.set_area(area)

    def on_object_selected(self):
        object = self.get_or_create_selector(OBJECT)
        self.check_emptiness(object)
        if not object.is_selected:
            return
        center = ((object.left_top + object.right_bottom) / 2).to_int()
        out_of_area = self._area_controller.point_is_out_of_area(center)
        if out_of_area:
            logger.warning('selected object is out of tracking borders')
            self._view_model.show_message('Нельзя выделять область за зоной слежения', 'Ошибка')
            self.stop_drawing_selected(object.name)
            return
        frame = self._current_frame
        self._tracker.start_tracking(frame, object.left_top, object.right_bottom)
        self._active_drawed_objects[OBJECT] = self._tracker
