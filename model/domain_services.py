from typing import List

from common.coordinates import Point
from common.logger import logger
from common.settings import settings, OBJECT, AREA
from common.thread_helpers import ThreadLoopable
from model.area_controller import AreaController
from model.camera_extractor import FrameExtractor
from model.frame_processing import Tracker, NoiseThresholdCalibrator
from model.move_controller import MoveController
from model.selector import RectSelector, TetragonSelector
from view.drawing import Processor, Drawable
from view.view_model import ViewModel
from view import view_output


MIN_THROTTLE_DIFFERENCE = 1


class SelectingService:
    def __init__(self):
        self._active_drawn_objects = dict()  # {name: Selector}
        self.object_is_selecting = False

    def load_selected_area(self, area, area_selected_callback):
        area_selector = TetragonSelector(AREA, area_selected_callback, area)
        if area_selector.is_empty:
            return
        area_selector._selected = True
        self._active_drawn_objects[AREA] = area_selector
        self.start_drawing_selected(area_selector)
        # TODO: убрать (upd: что убрать?)
        area_selected_callback()

    def stop_drawing_selected(self, name):
        if name in self._active_drawn_objects:
            del self._active_drawn_objects[name]

    def start_drawing_selected(self, selector):
        self._active_drawn_objects[selector.name] = selector

    def check_emptiness(self, selector):
        if selector.is_empty:
            logger.warning('selected area is zero in size')
            view_output.show_message('Область не может быть пустой или слишком малого размера', 'Ошибка')
            self.stop_drawing_selected(selector.name)

    def get_active_objects(self) -> List[Drawable]:
        return self._active_drawn_objects.values()

    def get_or_create_selector(self, name, area_selected_callback, object_selected_callback):
        selector = self._active_drawn_objects.get(name)
        if selector is None:
            logger.debug(f'creating new selector {name}')
            on_selected = object_selected_callback if OBJECT in name else area_selected_callback
            selector = RectSelector(name, on_selected) if OBJECT in name else TetragonSelector(name, on_selected)
            self._active_drawn_objects[name] = selector
        return selector


class LaserService():
    def __init__(self):
        self._laser_controller = MoveController(serial_off=False)

    def calibrate_laser(self):
        logger.debug('laser calibrated')
        self._laser_controller._move_laser(Point(0, 0), command=2)

    def center_laser(self):
        logger.debug('laser centered')
        self._laser_controller._move_laser(Point(0, 0))

    def move_laser(self, x, y):
        logger.debug(f'laser moved to {x, y}')
        self._laser_controller._move_laser(Point(x, y))

    def set_new_position(self, position: Point):
        self._laser_controller.set_new_position(position)


class Orchestrator(ThreadLoopable):

    def __init__(self, view_model: ViewModel, run_immediately: bool = True, area: tuple = None):
        self._view_model = view_model
        self._extractor = FrameExtractor(settings.CAMERA_ID)
        self.selecting_service = SelectingService()
        self._area_controller = AreaController(min_xy=-settings.MAX_LASER_RANGE_PLUS_MINUS,
                                               max_xy=settings.MAX_LASER_RANGE_PLUS_MINUS)
        self.tracker = Tracker(settings.TRACKING_FRAMES_MEAN_NUMBER)
        self.laser_service = LaserService()
        self._current_frame = None
        self.threshold_calibrator = NoiseThresholdCalibrator()
        self.previous_area = None

        if area is not None:
            self.selecting_service.load_selected_area(area, self.on_area_selected)
        FRAME_INTERVAL_SEC = 1 / settings.FPS_PROCESSED
        super().__init__(self._processing_loop, FRAME_INTERVAL_SEC, run_immediately)

    def get_or_create_selector(self, name):
        return self.selecting_service.get_or_create_selector(name, self.on_area_selected, self.on_object_selected)

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
            view_output.show_fatal(re)
        except Exception as e:
            view_output.show_fatal(e)
            logger.exception('Unexpected exception:')

    def _tracking_and_drawing(self, frame):
        if self.tracker.in_progress:
            self._tracking(frame)
        processed = Processor.draw_active_objects(frame, self.selecting_service.get_active_objects())
        return Processor.frame_to_image(processed)

    def _tracking(self, frame):
        center = self.tracker.get_tracked_position(frame)
        if not self.threshold_calibrator.in_progress:
            self._move_to_relative_cords(center)
            return
        if self.threshold_calibrator.is_calibration_successful(center):
            self.tracker.stop_tracking()
            self.selecting_service.stop_drawing_selected(OBJECT)
            self.selecting_service.start_drawing_selected(self.previous_area)
            self._area_controller.set_area(self.previous_area)
            self._view_model.progress_bar_set_visibility(False)
            settings.NOISE_THRESHOLD_PERCENT = round(settings.NOISE_THRESHOLD_PERCENT, 5)
            view_output.show_message('Калибровка успешно завершена')
        else:
            progress_value = self.threshold_calibrator.calibration_progress()
            if abs(self._view_model.progress_bar_get_value() - progress_value) > MIN_THROTTLE_DIFFERENCE:
                self._view_model.progress_bar_set_value(progress_value)

    def _move_to_relative_cords(self, center):
        out_of_area = self._area_controller.point_is_out_of_area(center, beep_sound=True)
        if not out_of_area:
            relative_coords = self._area_controller.calc_relative_coords(center)
            self.laser_service.set_new_position(relative_coords.to_int())

    def check_selected(self, name):
        selector = self.get_or_create_selector(name)
        self.selecting_service.check_emptiness(selector)
        if not selector.is_selected:
            return False, None
        return True, selector

    def on_area_selected(self):
        selected, area = self.check_selected(AREA)
        if not selected:
            self._view_model.new_selection(AREA, retry=True)
            return
        self._area_controller.set_area(area)

    def on_object_selected(self):
        selected, object = self.check_selected(OBJECT)
        out_of_area = True
        if selected:
            center = ((object.left_top + object.right_bottom) / 2).to_int()
            out_of_area = self._area_controller.point_is_out_of_area(center)
            if out_of_area:
                logger.warning('selected object is out of tracking borders')
                view_output.show_warning('Нельзя выделять объект за областью слежения')
                self.selecting_service.stop_drawing_selected(OBJECT)

        if not selected or out_of_area:
            self._view_model.new_selection(OBJECT, retry=True)
            return

        frame = self._current_frame
        self.tracker.start_tracking(frame, object.left_top, object.right_bottom)
        self.selecting_service.start_drawing_selected(self.tracker)
        self.selecting_service.object_is_selecting = False

    def new_selection(self, name, retry=False):
        if self.threshold_calibrator.in_progress and not retry:
            view_output.show_warning('Выполняется калибровка шумоподавления, необходимо дождаться её окончания')
            return

        if AREA in name and self.selecting_service.object_is_selecting:
            view_output.show_warning('Необходимо завершить выделение объекта')
            return

        self.selecting_service.stop_drawing_selected(name)

        if OBJECT in name:
            area = self.get_or_create_selector(AREA)
            if not area.is_selected:
                view_output.show_warning('Перед выделением объекта необходимо выделить область')
                return
            self.selecting_service.object_is_selecting = True

        if AREA in name:
            self.previous_area = self.get_or_create_selector(name)
            self.selecting_service.stop_drawing_selected(OBJECT)
        self.tracker.in_progress = False
        return self.get_or_create_selector(name)

    def calibrate_noise_threshold(self, width, height):
        self.previous_area = self.get_or_create_selector(AREA)
        self.selecting_service.stop_drawing_selected(AREA)
        area = self.get_or_create_selector(AREA)
        area._points = [Point(0, 0), Point(height, 0), Point(height, width), Point(0, width)]
        area._sort_points_for_viewing()
        area.is_selected = True
        self.on_area_selected()
        self._view_model.new_selection(OBJECT)
        self.threshold_calibrator.in_progress = True
        settings.NOISE_THRESHOLD_PERCENT = 0.0
        self._view_model.progress_bar_set_visibility(True)
        self._view_model.progress_bar_set_value(0)

    def calibrate_laser(self):
        # TODO: по возможности отрефакторить дублирование условий
        if not self.tracker.in_progress:
            self.laser_service.calibrate_laser()

    def center_laser(self):
        if self.tracker.in_progress:
            view_output.show_warning('Запрещено позиционирования лазера во время слежения за объектом')
            return
        self.laser_service.center_laser()

    def move_laser(self, x, y):
        if self.tracker.in_progress:
            view_output.show_warning('Запрещено позиционирования лазера во время слежения за объектом')
            return
        self.laser_service.move_laser(x, y)

    def stop_tracking(self):
        self.tracker.stop_tracking()
        self.selecting_service.stop_drawing_selected(OBJECT)

    def rotate_image(self, degree):
        # TODO: сделать запоминание угла поворота и режима отражения между запусками программы
        if self.tracker.in_progress:
            view_output.show_warning('Запрещено поворачивать изображение во время слежения за объектом')
        self._extractor.set_frame_rotate(degree)
        if degree in (90, 270):
            self._view_model.setup_window_geometry(reverse=True)
        else:
            self._view_model.setup_window_geometry(reverse=False)

    def flip_image(self, side):
        if self.tracker.in_progress:
            view_output.show_warning('Запрещено отражать зеркально изображение во время слежения за объектом')
        self._extractor.set_frame_flip(side)
