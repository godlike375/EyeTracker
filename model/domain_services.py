from time import time, sleep
from functools import partial

from common.logger import logger
from common.settings import settings, OBJECT, AREA, private_settings, \
    RESOLUTIONS, DOWNSCALED_HEIGHT
from common.thread_helpers import ThreadLoopable, MutableValue
from model.area_controller import AreaController
from model.camera_extractor import CameraService
from model.frame_processing import Tracker, NoiseThresholdCalibrator, CoordinateSystemCalibrator
from model.other_services import SelectingService, LaserService, StateTipSupervisor
from view import view_output
from view.drawing import Processor
from view.view_model import ViewModel
from common.program import exit_program


RESTART_IN_TIME_SEC = 10
# Пробовал увеличивать количество потоков в программе до 4-х (+ экстрактор + трекер в своих потоках)
# Итог: это только ухудшило производительность, так что больше 2-х потоков смысла иметь нет
# И запускать из цикла отрисовки вьюхи тоже смысла нет, т.к. это асинхронный цикл и будет всё тормозить


class Orchestrator(ThreadLoopable):

    def __init__(self, view_model: ViewModel, run_immediately: bool = True, area: tuple = None):
        self._view_model = view_model
        self.camera = CameraService(settings.CAMERA_ID)
        self.selecting = SelectingService(self._on_area_selected, self._on_object_selected)
        self.area_controller = AreaController(min_xy=-settings.MAX_LASER_RANGE_PLUS_MINUS,
                                              max_xy=settings.MAX_LASER_RANGE_PLUS_MINUS)
        self.tracker = Tracker(settings.MEAN_COORDINATES_FRAME_COUNT)
        self.state_tip = StateTipSupervisor(self._view_model)
        self.laser = LaserService(self.state_tip)

        self._current_frame = None
        self.threshold_calibrator = NoiseThresholdCalibrator(self, self._view_model)
        self.coordinate_calibrator = CoordinateSystemCalibrator(self, self._view_model)

        self.previous_area = None
        self._throttle_to_fps_viewed = time()
        self._frame_interval = MutableValue(1 / settings.FPS_VIEWED)
        self._fatal_error_count_repeatedly = 0
        self.rotate_image(private_settings.ROTATION_ANGLE, user_action=False)
        self.flip_image(private_settings.FLIP_SIDE, user_action=False)
        if self.camera.initialized:
            self.state_tip.change_tip('camera connected')
        if self.laser.initialized:
            self.state_tip.change_tip('laser connected')
        if area is not None:
            self.selecting.load_selected_area(area)

        super().__init__(self._processing_loop, self._frame_interval, run_immediately)

    def _processing_loop(self):
        try:
            frame = self.camera.extract_frame()
            if self.selecting.object_is_selecting or \
                    not Processor.frames_are_same(frame, self._current_frame):
                if self.tracker.in_progress:
                    self._tracking(frame)
                    if time() - self._throttle_to_fps_viewed < 1 / settings.FPS_VIEWED:
                        return
                    else:
                        self._throttle_to_fps_viewed = time()
                processed_image = self._draw_and_convert(self._resize_to_minimum(frame))
                self._fatal_error_count_repeatedly = 0
                self._view_model.on_image_ready(processed_image)
            self._current_frame = frame

        except RuntimeError as re:
            if 'dictionary changed size during iteration' in str(re):
                return
            if 'dictionary keys changed during iteration' in str(re):
                return
            view_output.show_fatal(re)
        except Exception as e:
            self._handle_fatal_error()
            view_output.show_fatal(e)
            logger.exception('Unexpected exception:')

    def _handle_fatal_error(self):
        self._fatal_error_count_repeatedly += 1
        if self._fatal_error_count_repeatedly > 2:
            view_output.show_error(f'В связи с множественными внутренними ошибками подключения и синхронизации '
                                   f' работа программы не может быть продолжена.'
                                   f' Программа перезапустится автоматически через {RESTART_IN_TIME_SEC} секунд')
            for i in range(RESTART_IN_TIME_SEC, 0, -1):
                sleep(1)
                self._view_model.set_tip(f'Перезапуск программы будет произведён через {i} секунд')
            self._view_model.execute_command(partial(exit_program, self, restart=True))

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
        object_relative_coords = self._move_to_relative_cords(center)
        if object_relative_coords is not None:
            self._view_model.set_tip(f'Текущие координаты объекта: '
                                     f'{object_relative_coords.x, object_relative_coords.y}')

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
        if result is not None:
            return relative_coords
        self.cancel_active_process(need_confirm=False)

    def _on_area_selected(self):
        selected, area = self.selecting.check_selected(AREA)
        if not selected:
            # TODO: если не выделялась вручную, то retry не нужен. Калибровку надо перезапускать
            self._view_model.new_selection(AREA, retry_select_object_in_calibrating=True)
            return
        self.previous_area = area
        self.area_controller.set_area(area, self.laser.laser_borders)
        self.state_tip.change_tip('area selected')

    def _on_object_selected(self, run_thread_after=None):
        selected, object = self.selecting.check_selected(OBJECT)
        out_of_area = False
        if selected and not (self.threshold_calibrator.in_progress or self.coordinate_calibrator.in_progress):
            center = ((object.left_top + object.right_bottom) / 2).to_int()
            out_of_area = self.area_controller.point_is_out_of_area(center)
            if out_of_area:
                view_output.show_error('Невозможно выделить объект за границами области слежения.')
                self.selecting.stop_drawing(OBJECT)

        if not selected or out_of_area:
            self._view_model.new_selection(OBJECT, retry_select_object_in_calibrating=True,
                                           additional_callback=run_thread_after)
            return

        self.tracker.start_tracking(self._current_frame, object.left_top, object.right_bottom)
        self.selecting.start_drawing(self.tracker, OBJECT)
        self.selecting.object_is_selecting = False
        self._frame_interval.value = 1 / settings.FPS_PROCESSED
        self.state_tip.change_tip('object selected')
        if run_thread_after is not None:
            run_thread_after().start()

    def _new_object(self, select_in_calibrating):
        if select_in_calibrating:
            self.selecting.object_is_selecting = True
            return True

        if not self.selecting.selector_is_selected(AREA):
            view_output.show_error('Перед выделением объекта необходимо откалибровать координатную систему.')
            return False

        if self.laser.errored:
            view_output.show_error(
                'Необходимо откалибровать контроллер лазера повторно. '
                'До этого момента слежение за объектом невозможно.')
            self.state_tip.change_tip('laser calibrated', False)
            return False
        if self.selecting.selector_is_selected(OBJECT):
            confirm = view_output.ask_confirmation('Выделенный объект перестанет отслеживаться. Продолжить?')
            if not confirm:
                return False

        self.selecting.object_is_selecting = True
        return True

    def _new_area(self, dont_reselect_area):
        # TODO: поправить логику и сделать без костылей вроде этого
        if dont_reselect_area:
            return False
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
            if not self._new_object(retry_select_object_in_calibrating):
                return

        if AREA in name:
            if not self._new_area(dont_reselect_area=retry_select_object_in_calibrating):
                return

        self.selecting.stop_drawing(name)

        self.tracker.in_progress = False
        return self.selecting.create_selector(name, additional_callback)

    def calibrate_noise_threshold(self):
        if self.tracker.in_progress:
            view_output.show_error('Калибровка шумоподавления во время слежения за объектом невозможна.')
            return

        if self.selecting.selector_is_selected(AREA):
            self.previous_area = self.selecting.get_selector(AREA)
            self.selecting.stop_drawing(AREA)

        self.threshold_calibrator.start()
        self._view_model.new_selection(OBJECT, retry_select_object_in_calibrating=True,
                                       additional_callback=self.threshold_calibrator.calibrate)

        settings.NOISE_THRESHOLD_PERCENT = 0.0

        self._view_model.progress_bar_set_visibility(True)
        self._view_model.set_progress(0)

    def calibrate_coordinate_system(self):
        if self.tracker.in_progress:
            view_output.show_error('Калибровка координатной системы во время слежения за объектом невозможна.')
            return

        if self.selecting.selector_is_selected(AREA):
            self.previous_area = self.selecting.get_selector(AREA)
            self.selecting.stop_drawing(AREA)

        self.coordinate_calibrator.start()
        self._view_model.new_selection(OBJECT, retry_select_object_in_calibrating=True,
                                       additional_callback=self.coordinate_calibrator.calibrate)
        self._view_model.progress_bar_set_visibility(True)
        self._view_model.set_progress(0)

    def calibrate_laser(self):
        # TODO: по возможности отрефакторить дублирование условий
        if self.tracker.in_progress:
            view_output.show_error('Калибровка лазера во время слежения за объектом невозможна.')
            return
        self.laser.calibrate_laser()
        self.state_tip.change_tip('laser calibrated')

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

    def cancel_active_process(self, need_confirm=True):
        if need_confirm:
            if self.selecting.object_is_selecting or \
                    self.threshold_calibrator.in_progress or \
                    self.tracker.in_progress:
                need_confirm = view_output.ask_confirmation('Прервать активный процесс?')
                if not need_confirm:
                    return
        self.selecting.cancel_selecting()
        self.threshold_calibrator.stop()
        self.tracker.stop()
        self.coordinate_calibrator.stop()
        self.selecting.stop_drawing(OBJECT)
        self.restore_previous_area()
        settings.NOISE_THRESHOLD_PERCENT = 0.0
        self._frame_interval.value = 1 / settings.FPS_VIEWED
        self.state_tip.change_tip('area selected')
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
        self.cancel_active_process(need_confirm=False)
        self.selecting.stop_drawing(AREA)
        self.previous_area = None
        self.camera.set_frame_rotate(degree)
        if degree in (90, 270):
            self._view_model.setup_window_geometry(reverse=True)
        else:
            self._view_model.setup_window_geometry(reverse=False)
        self._view_model.set_rotate_angle(degree)


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
        self.cancel_active_process(need_confirm=False)
        self.selecting.stop_drawing(AREA)
        self.previous_area = None
        self.camera.set_frame_flip(side)
        self._view_model.set_flip_side(side)

    def stop_thread(self):
        self.coordinate_calibrator.stop()
        super(Orchestrator, self).stop_thread()
