from time import time

from common.coordinates import Point
from common.logger import logger
from common.settings import settings, OBJECT, AREA, private_settings, \
    RESOLUTIONS, DOWNSCALED_HEIGHT, MIN_THROTTLE_DIFFERENCE
from common.thread_helpers import ThreadLoopable, MutableValue
from model.area_controller import AreaController
from model.camera_extractor import FrameExtractor
from model.frame_processing import Tracker, NoiseThresholdCalibrator, CoordinateSystemCalibrator
from model.other_services import SelectingService, LaserService, StateTipSupervisor
from view import view_output
from view.drawing import Processor
from view.view_model import ViewModel


# Пробовал увеличивать количество потоков в программе до 4-х (+ экстрактор + трекер в своих потоках)
# Итог: это только ухудшило производительность, так что больше 2-х потоков смысла иметь нет
# И запускать из цикла отрисовки вьюхи тоже смысла нет, т.к. это асинхронный цикл и будет всё тормозить


class Orchestrator(ThreadLoopable):

    def __init__(self, view_model: ViewModel, run_immediately: bool = True, area: tuple = None):
        self._view_model = view_model
        self._extractor = FrameExtractor(settings.CAMERA_ID)
        self.selecting_service = SelectingService(self._on_area_selected, self._on_object_selected)
        self._area_controller = AreaController(min_xy=-settings.MAX_LASER_RANGE_PLUS_MINUS,
                                               max_xy=settings.MAX_LASER_RANGE_PLUS_MINUS)
        self.tracker = Tracker(settings.TRACKING_FRAMES_MEAN_NUMBER)
        self.laser_service = LaserService()
        self.state_tip = StateTipSupervisor(self._view_model)

        self._current_frame = None
        self.threshold_calibrator = NoiseThresholdCalibrator()
        self.coordinate_system_calibrator = CoordinateSystemCalibrator(self.laser_service, self.selecting_service,
                                                                       self._area_controller, self.tracker)

        self.previous_area = None
        self._throttle_to_fps_viewed = time()
        self._frame_interval = MutableValue(1 / settings.FPS_VIEWED)
        self.rotate_image(private_settings.ROTATION_ANGLE, user_action=False)
        self.flip_image(private_settings.FLIP_SIDE, user_action=False)
        if self._extractor.initialized and self.laser_service.initialized:
            self.state_tip.next_state('devices connected')
        if area is not None:
            self.selecting_service.load_selected_area(area)

        super().__init__(self._processing_loop, self._frame_interval, run_immediately)

    def _processing_loop(self):
        try:
            frame = self._extractor.extract_frame()
            if self.selecting_service.object_is_selecting or \
                    not Processor.frames_are_same(frame, self._current_frame):
                if self.tracker.in_progress:
                    self._tracking(frame)
                    if time() - self._throttle_to_fps_viewed < 1 / settings.FPS_VIEWED:
                        return
                    else:
                        self._throttle_to_fps_viewed = time()
                processed_image = self._draw_and_convert(self._resize_to_minimum(frame))
                self._view_model.on_image_ready(processed_image)
            self._current_frame = frame

        except RuntimeError as re:
            if 'dictionary changed size during iteration' in str(re):
                return
            if 'dictionary keys changed during iteration' in str(re):
                return
            view_output.show_fatal(re)
        except Exception as e:
            view_output.show_fatal(e)
            logger.exception('Unexpected exception:')

    def _resize_to_minimum(self, frame):
        frame_width = frame.shape[0]
        frame_height = frame.shape[1]
        if frame_height == DOWNSCALED_HEIGHT or frame_width == DOWNSCALED_HEIGHT:
            return frame
        reversed = frame_height < frame_width
        down_width = RESOLUTIONS[DOWNSCALED_HEIGHT]
        if reversed:
            return Processor.resize_frame_absolute(frame, DOWNSCALED_HEIGHT, down_width)
        return Processor.resize_frame_absolute(frame, down_width, DOWNSCALED_HEIGHT)

    def _draw_and_convert(self, frame):
        processed = Processor.draw_active_objects(frame, self.selecting_service.get_active_objects())
        return Processor.frame_to_image(processed)

    def _threshold_calibrating(self, center):
        if self.threshold_calibrator.is_calibration_successful(center):
            self._noise_threshold_calibrated()
        else:
            progress_value = self.threshold_calibrator.calibration_progress()
            if abs(self._view_model.progress_bar_get_value() - progress_value) > MIN_THROTTLE_DIFFERENCE:
                self._view_model.progress_bar_set_value(progress_value)

    def _tracking(self, frame):
        center = self.tracker.get_tracked_position(frame)
        if self.threshold_calibrator.in_progress:
            self._threshold_calibrating(center)
            return
        if self.coordinate_system_calibrator.in_progress:
            return
        self._move_to_relative_cords(center)

    def _noise_threshold_calibrated(self):
        self.tracker.stop()
        self.selecting_service.stop_drawing(OBJECT)
        self._restore_previous_area()
        settings.NOISE_THRESHOLD_PERCENT = round(settings.NOISE_THRESHOLD_PERCENT, 5)
        self.state_tip.next_state('noise threshold calibrated')
        view_output.show_message('Калибровка шумоподавления успешно завершена.')

    def _restore_previous_area(self):
        if self.previous_area is not None:
            self.selecting_service.start_drawing(self.previous_area, AREA)
            self._area_controller.set_area(self.previous_area)
        self._view_model.progress_bar_set_visibility(False)

    def _move_to_relative_cords(self, center):
        out_of_area = self._area_controller.point_is_out_of_area(center, beep_sound_allowed=True)
        if out_of_area:
            return

        relative_coords = self._area_controller.calc_laser_coords(center)
        result = self.laser_service.set_new_position(relative_coords)
        if result is None:
            self.cancel_active_process(confirm=False)

    def _on_area_selected(self):
        selected, area = self.selecting_service.check_selected(AREA)
        if not selected:
            self._view_model.new_selection(AREA, retry=True)
            return
        self.previous_area = area
        self._area_controller.set_area(area)
        self.state_tip.next_state('area selected')

    def _on_object_selected(self):
        selected, object = self.selecting_service.check_selected(OBJECT)
        out_of_area = False
        if selected:
            center = ((object.left_top + object.right_bottom) / 2).to_int()
            out_of_area = self._area_controller.point_is_out_of_area(center)
            if out_of_area:
                logger.warning('selected object is out of tracking borders')
                view_output.show_warning('Невозможно выделить объект за границами области слежения.')
                self.selecting_service.stop_drawing(OBJECT)

        if not selected or out_of_area:
            self._view_model.new_selection(OBJECT, retry=True)
            return

        self.tracker.start_tracking(self._current_frame, object.left_top, object.right_bottom)
        self.selecting_service.start_drawing(self.tracker, OBJECT)
        self.selecting_service.object_is_selecting = False
        self._frame_interval.value = 1 / settings.FPS_PROCESSED
        self.state_tip.next_state('object selected')

    def _new_object(self):
        if not self.selecting_service.selector_is_selected(AREA):
            view_output.show_warning('Перед выделением объекта необходимо выделить область слежения.')
            return False

        if self.laser_service.errored:
            view_output.show_warning(
                'Необходимо откалибровать контроллер лазера повторно. '
                'До этого момента слежения за объектом невозможно')
            return False
        if self.selecting_service.selector_is_selected(OBJECT):
            confirm = view_output.ask_confirmation('Выделенный объект перестанет отслеживаться. Продолжить?')
            if not confirm:
                return False

        self.selecting_service.object_is_selecting = True

    def _new_area(self):
        if self.selecting_service.object_is_selecting:
            view_output.show_warning('Необходимо завершить выделение объекта.')
            return False

        tracking_stop_question = ''
        if self.selecting_service.selector_is_selected(OBJECT):
            tracking_stop_question = 'Слежение за целью будет остановлено. '
        if self.selecting_service.selector_is_selected(AREA):
            confirm = view_output.ask_confirmation(f'{tracking_stop_question}'
                                                   f'Выделенная область будет стёрта. Продолжить?')
            if not confirm:
                return False
        self.selecting_service.stop_drawing(OBJECT)

    def new_selection(self, name, retry=False, additional_callback=None):
        if self.threshold_calibrator.in_progress and not retry:
            view_output.show_warning('Выполняется калибровка шумоподавления, необходимо дождаться её окончания.')
            return

        if OBJECT in name:
            if not self._new_object():
                return

        if AREA in name:
            if not self._new_area():
                return

        self.selecting_service.stop_drawing(name)

        self.tracker.in_progress = False
        return self.selecting_service.create_selector(name, additional_callback)

    def _auto_select_area_full_screen(self, width, height):
        # TODO: перенести кроме последней строчки в SelectingService
        area = self.selecting_service.create_selector(AREA)
        area._points = [Point(0, 0), Point(height, 0), Point(height, width), Point(0, width)]
        area._sort_points_for_viewing()
        area.is_selected = True
        self._area_controller.set_area(area)

    def _auto_select_area(self, points):
        area = self.selecting_service.create_selector(AREA)
        area._points = points
        area._sort_points_for_viewing()
        area.is_selected = True
        self._area_controller.set_area(area)

    def calibrate_noise_threshold(self, width, height):
        if self.tracker.in_progress:
            view_output.show_warning('Запрещена калибровка шумоподавления во время слежения за объектом.')
            return

        if self.selecting_service.selector_is_selected(AREA):
            self.previous_area = self.selecting_service.get_selector(AREA)
            self.selecting_service.stop_drawing(AREA)

        self._auto_select_area_full_screen(width, height)
        self._view_model.new_selection(OBJECT)

        self.threshold_calibrator.start()
        settings.NOISE_THRESHOLD_PERCENT = 0.0

        self._view_model.progress_bar_set_visibility(True)
        self._view_model.progress_bar_set_value(0)

    def calibrate_coordinate_system(self, width, height):
        if self.tracker.in_progress:
            view_output.show_warning('Запрещена калибровка координатной системы во время слежения за объектом.')
            return

        self._auto_select_area_full_screen(width, height)
        self._view_model.new_selection(OBJECT, retry=False,
                                       additional_callback=self.coordinate_system_calibrator.calibrate)
        self.coordinate_system_calibrator.start()
        self._view_model.progress_bar_set_visibility(True)
        self._view_model.progress_bar_set_value(0)

    def calibrate_laser(self):
        # TODO: по возможности отрефакторить дублирование условий
        if self.tracker.in_progress:
            view_output.show_warning('Запрещена калибровка лазера во время слежения за объектом.')
            return
        self.laser_service.calibrate_laser()
        self.state_tip.next_state('laser calibrated')

    def center_laser(self):
        if self.tracker.in_progress:
            view_output.show_warning('Запрещено позиционирования лазера во время слежения за объектом.')
            return
        self.laser_service.center_laser()

    def move_laser(self, x, y):
        if self.tracker.in_progress:
            view_output.show_warning('Запрещено позиционирования лазера во время слежения за объектом.')
            return
        self.laser_service.move_laser(x, y)

    def cancel_active_process(self, confirm=True):
        if confirm:
            if self.selecting_service.object_is_selecting or \
                    self.threshold_calibrator.in_progress or \
                    self.tracker.in_progress:
                confirm = view_output.ask_confirmation('Прервать активный процесс?')
                if not confirm:
                    return
        self.selecting_service.cancel_selecting()
        self.threshold_calibrator.stop()
        self.tracker.stop()
        self.coordinate_system_calibrator.stop()
        self.selecting_service.stop_drawing(OBJECT)
        self._restore_previous_area()
        settings.NOISE_THRESHOLD_PERCENT = 0.0
        self._frame_interval.value = 1 / settings.FPS_VIEWED
        self.state_tip.next_state('area selected')
        Processor.load_color()

    def rotate_image(self, degree, user_action=True):
        if self.tracker.in_progress:
            view_output.show_warning('Запрещено поворачивать изображение во время слежения за объектом')
            return

        if private_settings.ROTATION_ANGLE == degree and user_action:
            return

        if self.selecting_service.selector_is_selected(AREA):
            confirm = view_output.ask_confirmation('Выделенная область будет стёрта. Продолжить?')
            if not confirm:
                return

        private_settings.ROTATION_ANGLE = degree
        self.cancel_active_process(confirm=False)
        self.selecting_service.stop_drawing(AREA)
        self._extractor.set_frame_rotate(degree)
        if degree in (90, 270):
            self._view_model.setup_window_geometry(reverse=True)
        else:
            self._view_model.setup_window_geometry(reverse=False)
        self.previous_area = None

    def flip_image(self, side, user_action=True):
        if self.tracker.in_progress:
            view_output.show_warning('Запрещено отражать зеркально изображение во время слежения за объектом')
            return

        if private_settings.FLIP_SIDE == side and user_action:
            return

        if self.selecting_service.selector_is_selected(AREA):
            confirm = view_output.ask_confirmation('Выделенная область будет стёрта. Продолжить?')
            if not confirm:
                return

        private_settings.FLIP_SIDE = side
        self.cancel_active_process(confirm=False)
        self.selecting_service.stop_drawing(AREA)
        self._extractor.set_frame_flip(side)
        self.previous_area = None

    def stop_thread(self):
        self.coordinate_system_calibrator.stop()
        super(Orchestrator, self).stop_thread()
