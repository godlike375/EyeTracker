from time import time

from common.coordinates import Point
from common.logger import logger
from common.settings import settings, OBJECT, AREA, private_settings, \
    RESOLUTIONS, DOWNSCALED_HEIGHT
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
        self.selecting = SelectingService(self._on_area_selected, self._on_object_selected)
        self.area_controller = AreaController(min_xy=-settings.MAX_LASER_RANGE_PLUS_MINUS,
                                              max_xy=settings.MAX_LASER_RANGE_PLUS_MINUS)
        self.tracker = Tracker(settings.TRACKING_FRAMES_MEAN_NUMBER)
        self.laser = LaserService()
        self.state_tip = StateTipSupervisor(self._view_model)

        self._current_frame = None
        self.threshold_calibrator = NoiseThresholdCalibrator(self, self._view_model)
        self.coordinate_calibrator = CoordinateSystemCalibrator(self, self._view_model)

        self.previous_area = None
        self._throttle_to_fps_viewed = time()
        self._frame_interval = MutableValue(1 / settings.FPS_VIEWED)
        self.rotate_image(private_settings.ROTATION_ANGLE, user_action=False)
        self.flip_image(private_settings.FLIP_SIDE, user_action=False)
        if self._extractor.initialized and self.laser.initialized:
            self.state_tip.next_state('devices connected')
        if area is not None:
            self.selecting.load_selected_area(area)

        super().__init__(self._processing_loop, self._frame_interval, run_immediately)

    def _processing_loop(self):
        try:
            frame = self._extractor.extract_frame()
            if self.selecting.object_is_selecting or \
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
        processed = Processor.draw_active_objects(frame, self.selecting.get_active_objects())
        return Processor.frame_to_image(processed)

    def _tracking(self, frame):
        center = self.tracker.get_tracked_position(frame)
        if self.coordinate_calibrator.in_progress or self.threshold_calibrator.in_progress:
            return
        self._move_to_relative_cords(center)

    def restore_previous_area(self):
        if self.previous_area is not None:
            self.selecting.start_drawing(self.previous_area, AREA)
            self.area_controller.set_area(self.previous_area, self.laser.laser_borders)
        self._view_model.progress_bar_set_visibility(False)

    def _move_to_relative_cords(self, center):
        out_of_area = self.area_controller.point_is_out_of_area(center, beep_sound_allowed=True)
        if out_of_area:
            return

        relative_coords = self.area_controller.calc_laser_coords(center)
        result = self.laser.set_new_position(relative_coords)
        if result is None:
            self.cancel_active_process(confirm=False)

    def _on_area_selected(self):
        selected, area = self.selecting.check_selected(AREA)
        if not selected:
            self._view_model.new_selection(AREA, retry_select_object_in_calibrating=True)
            return
        self.previous_area = area
        self.area_controller.set_area(area, self.laser.laser_borders)
        self.state_tip.next_state('area selected')

    def _on_object_selected(self):
        selected, object = self.selecting.check_selected(OBJECT)
        out_of_area = False
        if selected:
            center = ((object.left_top + object.right_bottom) / 2).to_int()
            out_of_area = self.area_controller.point_is_out_of_area(center)
            if out_of_area:
                view_output.show_error('Невозможно выделить объект за границами области слежения.')
                self.selecting.stop_drawing(OBJECT)

        if not selected or out_of_area:
            self._view_model.new_selection(OBJECT, retry_select_object_in_calibrating=True)
            return

        self.tracker.start_tracking(self._current_frame, object.left_top, object.right_bottom)
        self.selecting.start_drawing(self.tracker, OBJECT)
        self.selecting.object_is_selecting = False
        self._frame_interval.value = 1 / settings.FPS_PROCESSED
        self.state_tip.next_state('object selected')

    def _new_object(self):
        if not self.selecting.selector_is_selected(AREA):
            view_output.show_error('Перед выделением объекта необходимо выделить область слежения.')
            return False

        if self.laser.errored:
            view_output.show_error(
                'Необходимо откалибровать контроллер лазера повторно. '
                'До этого момента слежения за объектом невозможно.')
            return False
        if self.selecting.selector_is_selected(OBJECT):
            confirm = view_output.ask_confirmation('Выделенный объект перестанет отслеживаться. Продолжить?')
            if not confirm:
                return False

        self.selecting.object_is_selecting = True
        return True

    def _new_area(self):
        if self.selecting.object_is_selecting:
            view_output.show_warning('Необходимо завершить выделение объекта.')
            return False

        tracking_stop_question = ''
        if self.selecting.selector_is_selected(OBJECT):
            tracking_stop_question = 'Слежение за целью будет остановлено. '
        if self.selecting.selector_is_selected(AREA):
            confirm = view_output.ask_confirmation(f'{tracking_stop_question}'
                                                   f'Выделенная область будет стёрта. Продолжить?')
            if not confirm:
                return False
        self.selecting.stop_drawing(OBJECT)
        return True

    def new_selection(self, name, retry_select_object_in_calibrating=False, additional_callback=None):
        if (self.threshold_calibrator.in_progress or self.coordinate_calibrator.in_progress)\
                and not retry_select_object_in_calibrating:
            view_output.show_warning('Выполняется процесс калибровки, необходимо дождаться его окончания.')
            return

        if OBJECT in name:
            if not self._new_object():
                return

        if AREA in name:
            if not self._new_area():
                return

        self.selecting.stop_drawing(name)

        self.tracker.in_progress = False
        return self.selecting.create_selector(name, additional_callback)

    def _auto_select_area_full_screen(self, width, height):
        # TODO: перенести кроме последней строчки в SelectingService
        # TODO: подумать, мб вообще не нужно выделять на весь экран область, ибо это выглядит как костыль
        #  и заставляет потом restore делать. Когда можно вообще всего этого не делать, позволив следить за объектом
        #  без выделения области
        area = self.selecting.create_selector(AREA)
        area._points = [Point(0, 0), Point(height, 0), Point(height, width), Point(0, width)]
        area._sort_points_for_viewing()
        area.is_selected = True
        self.area_controller.set_area(area, self.laser.laser_borders)

    def calibrate_noise_threshold(self, width, height):
        if self.tracker.in_progress:
            view_output.show_error('Калибровка шумоподавления во время слежения за объектом невозможна.')
            return

        if self.selecting.selector_is_selected(AREA):
            self.previous_area = self.selecting.get_selector(AREA)
            self.selecting.stop_drawing(AREA)

        self._auto_select_area_full_screen(width, height)
        self._view_model.new_selection(OBJECT, retry_select_object_in_calibrating=False,
                                       additional_callback=self.threshold_calibrator.calibrate)

        self.threshold_calibrator.start()
        settings.NOISE_THRESHOLD_PERCENT = 0.0

        self._view_model.progress_bar_set_visibility(True)
        self._view_model.set_progress(0)

    def calibrate_coordinate_system(self, width, height):
        if self.tracker.in_progress:
            view_output.show_error('Калибровка координатной системы во время слежения за объектом невозможна.')
            return

        self._auto_select_area_full_screen(width, height)
        self._view_model.new_selection(OBJECT, retry_select_object_in_calibrating=False,
                                       additional_callback=self.coordinate_calibrator.calibrate)
        self.coordinate_calibrator.start()
        self._view_model.progress_bar_set_visibility(True)
        self._view_model.set_progress(0)

    def calibrate_laser(self):
        # TODO: по возможности отрефакторить дублирование условий
        if self.tracker.in_progress:
            view_output.show_error('Калибровка лазера во время слежения за объектом невозможна.')
            return
        self.laser.calibrate_laser()
        self.state_tip.next_state('laser calibrated')

    def center_laser(self):
        if self.tracker.in_progress:
            view_output.show_error('Позиционирование лазера во время слежения за объектом невозможно.')
            return
        self.laser.center_laser()

    def move_laser(self, x, y):
        if self.tracker.in_progress:
            view_output.show_error('Позиционирование лазера во время слежения за объектом невозможно.')
            return
        self.laser.move_laser(x, y)

    def cancel_active_process(self, confirm=True):
        if confirm:
            if self.selecting.object_is_selecting or \
                    self.threshold_calibrator.in_progress or \
                    self.tracker.in_progress:
                confirm = view_output.ask_confirmation('Прервать активный процесс?')
                if not confirm:
                    return
        self.selecting.cancel_selecting()
        self.threshold_calibrator.stop()
        self.tracker.stop()
        self.coordinate_calibrator.stop()
        self.selecting.stop_drawing(OBJECT)
        self.restore_previous_area()
        settings.NOISE_THRESHOLD_PERCENT = 0.0
        self._frame_interval.value = 1 / settings.FPS_VIEWED
        self.state_tip.next_state('area selected')
        Processor.load_color()

    def rotate_image(self, degree, user_action=True):
        if self.tracker.in_progress:
            view_output.show_error('Поворот изображения во время слежения за объектом невозможен.')
            return

        if private_settings.ROTATION_ANGLE == degree and user_action:
            return

        if self.selecting.selector_is_selected(AREA):
            confirm = view_output.ask_confirmation('Выделенная область будет стёрта. Продолжить?')
            if not confirm:
                return

        private_settings.ROTATION_ANGLE = degree
        self.cancel_active_process(confirm=False)
        self.selecting.stop_drawing(AREA)
        self._extractor.set_frame_rotate(degree)
        if degree in (90, 270):
            self._view_model.setup_window_geometry(reverse=True)
        else:
            self._view_model.setup_window_geometry(reverse=False)
        self.previous_area = None

    def flip_image(self, side, user_action=True):
        if self.tracker.in_progress:
            view_output.show_error('Отражение изображения во время слежения за объектом невозможно.')
            return

        if private_settings.FLIP_SIDE == side and user_action:
            return

        if self.selecting.selector_is_selected(AREA):
            confirm = view_output.ask_confirmation('Выделенная область будет стёрта. Продолжить?')
            if not confirm:
                return

        private_settings.FLIP_SIDE = side
        self.cancel_active_process(confirm=False)
        self.selecting.stop_drawing(AREA)
        self._extractor.set_frame_flip(side)
        self.previous_area = None

    def stop_thread(self):
        self.coordinate_calibrator.stop()
        super(Orchestrator, self).stop_thread()
