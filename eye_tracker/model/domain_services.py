import sys
from time import time, sleep

from eye_tracker.common.logger import logger
from eye_tracker.common.program import exit_program
from eye_tracker.common.settings import settings, OBJECT, AREA, private_settings, MAX_LASER_RANGE
from eye_tracker.common.thread_helpers import ThreadLoopable, MutableValue
from eye_tracker.model.area_controller import AreaController
from eye_tracker.model.camera_extractor import CameraService
from eye_tracker.model.frame_processing import Tracker
from eye_tracker.model.move_controller import MoveController
from eye_tracker.model.other_services import SelectingService, StateMachine, OnScreenService, \
    NoiseThresholdCalibrator, CoordinateSystemCalibrator
from eye_tracker.view import view_output
from eye_tracker.view.drawing import Processor
from eye_tracker.view.view_model import ViewModel


# WARNING: Пробовал увеличивать количество потоков в программе до 4-х (+ экстрактор + трекер в своих потоках)
#  Итог: это только ухудшило производительность, так что больше 2-х потоков смысла иметь нет
#  И запускать из цикла отрисовки вьюхи тоже смысла нет, т.к. это асинхронный цикл и будет всё тормозить


class ErrorHandler:
    RESTART_IN_TIME_SEC = 10

    def __init__(self, view_model, model):
        self._fatal_error_count_repeatedly = 0
        self._view_model = view_model
        self._model = model

    def _handle_fatal_error(self, error):
        self._fatal_error_count_repeatedly += 1
        if self._fatal_error_count_repeatedly > 2:
            view_output.show_error \
                    (
                    f'В связи с множественными внутренними ошибками вида:\n\n'
                    f'[ {error} ] работа программы не может быть продолжена.\n\n'
                    f'Программа перезапустится автоматически через {ErrorHandler.RESTART_IN_TIME_SEC} секунд.',
                    timeout=10500
                )
            for i in range(ErrorHandler.RESTART_IN_TIME_SEC, 0, -1):
                sleep(1)
                self._view_model.set_tip(f'Перезапуск программы будет произведён через {i} секунд')
            self._view_model.execute_command(sys.exit)
            logger.debug('fatal error')
            exit_program(self._model, restart=True)

    def handle_exceptions(self, func):
        def wrapper(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except Exception as e:
                if 'dictionary changed size during iteration' in str(e):
                    return
                if 'dictionary keys changed during iteration' in str(e):
                    return
                logger.exception('Unexpected exception:')
                self._handle_fatal_error(e)
            else:
                self._fatal_error_count_repeatedly = 0

        return wrapper


class Orchestrator(ThreadLoopable):

    def __init__(self, view_model: ViewModel, run_immediately: bool = True, area: tuple = None, debug_on=False,
                 camera=None, laser=None):
        self._view_model = view_model
        self._error_handler = ErrorHandler(view_model, self)
        self._processing_loop = self._error_handler.handle_exceptions(self._processing_loop)  # manual decoration

        self.camera = camera or CameraService(settings.CAMERA_ID)
        self.area_controller = AreaController(min_xy=-MAX_LASER_RANGE,
                                              max_xy=MAX_LASER_RANGE)
        self.tracker = Tracker(settings.MEAN_COORDINATES_FRAME_COUNT)
        self.state_control = StateMachine(self._view_model)
        self.screen = OnScreenService(self)
        self.selecting = SelectingService(self._on_area_selected, self._on_object_selected, self, self.screen,
                                          self._view_model)
        self.laser = laser or MoveController(self._on_laser_error, debug_on=debug_on)

        self._current_frame = None
        self.filtered_ranges = None

        self.calibrators = {'noise threshold': NoiseThresholdCalibrator(self, self._view_model),
                            'coordinate system': CoordinateSystemCalibrator(self, self._view_model)}

        self.previous_area = None
        self._throttle_to_fps_viewed = time()
        self._frame_interval = MutableValue(1 / settings.FPS_VIEWED)

        self.rotate_image(private_settings.ROTATION_ANGLE, user_action=False)
        self.flip_image(private_settings.FLIP_SIDE, user_action=False)
        self._view_model.set_menu_state('all', 'normal')
        if self.camera.initialized:
            self.state_control.change_state('camera connected')
        if self.laser.initialized:
            self.state_control.change_state('laser connected')
        if area is not None:
            self.selecting.load_selected_area(area)

        self.calibrate_laser()

        super().__init__(self._processing_loop, self._frame_interval, run_immediately)

    def _processing_loop(self):
        frame = self.camera.extract_frame()
        if self.filtered_ranges is not None:
            lower, upper = self.filtered_ranges
            #frame = Processor.bgr_to_hsv(frame)
            #frame = Processor.replace_hsv_range(frame, int(lower[0]), int(upper[0]), 0)
            #frame = Processor.hsv_to_bgr(frame)
            #frame = Processor.blur_image(frame)
        if self.selecting.selecting_in_progress(OBJECT) \
                or not Processor.frames_are_same(frame, self._current_frame):
            if self.tracker.in_progress:
                self._tracking(frame)
                if time() - self._throttle_to_fps_viewed < 1 / settings.FPS_VIEWED:
                    return
                else:
                    self._throttle_to_fps_viewed = time()
            processed_image = self.screen.prepare_image(frame)
            self._view_model.on_image_ready(processed_image)
        self._current_frame = frame

    def _calibrating_in_progress(self):
        return any([i.in_progress for i in self.calibrators.values()])

    def _tracking(self, frame):
        center = self.tracker.get_tracked_position(frame)
        if self._calibrating_in_progress():
            return
        object_relative_coords = self._move_to_relative_cords(center)
        if self.tracker.in_progress:
        # проверка нужна из-за многопоточности, чтобы лучше была синхронизация и меньше шанс,
        # что координаты выведутся после прерывания процесса и собьют вывод подсказки
            if object_relative_coords is not None:
                self._view_model.set_tip(f'Текущие координаты объекта: '
                                     f'{object_relative_coords.x, object_relative_coords.y}')
            else:
                self._view_model.set_tip(f'Объект вышел за границы допустимой области движения лазера')

    def try_restore_previous_area(self):
        if self.previous_area is not None:
            self.screen.add_selector(self.previous_area, AREA)
            self.area_controller.set_area(self.previous_area, self.laser.laser_borders)
        self._view_model.progress_bar_set_visibility(False)

    def _move_to_relative_cords(self, center):
        out_of_area = self.area_controller.point_is_out_of_area(center, beep_sound_allowed=True)
        if out_of_area:
            return

        relative_coords = self.area_controller.calc_laser_coords(center)
        self.laser.set_new_position(relative_coords)
        return relative_coords

    def _on_laser_error(self):
        self.cancel_active_process(need_confirm=False)
        self.state_control.change_state('laser calibrated', False)

    def _on_area_selected(self):
        selected, area = self.selecting.check_selected_correctly(AREA)
        if not selected:
            # TODO: если не выделялась вручную, то retry не нужен. Калибровку надо перезапускать
            self._view_model.new_selection(AREA, reselect_while_calibrating=True)
            self._view_model.set_menu_state('all', 'normal')
            return
        self._view_model.set_menu_state('all', 'normal')
        self.previous_area = area
        self.area_controller.set_area(area, self.laser.laser_borders)
        self.state_control.change_state('coordinate system calibrated')

    def _on_object_selected(self, run_thread_after=None):
        selected, object = self.selecting.check_selected_correctly(OBJECT)
        out_of_area = False
        if selected and not (self._calibrating_in_progress()):
            out_of_area = self.area_controller.point_is_out_of_area(object.center)
            if out_of_area:
                view_output.show_error('Невозможно выделить объект за границами области слежения.')
                self.screen.remove_selector(OBJECT)

        if not selected or out_of_area:
            self._view_model.new_selection(OBJECT, reselect_while_calibrating=True,
                                           additional_callback=run_thread_after)
            return

        self.tracker.start_tracking(self._current_frame, object.left_top, object.right_bottom)
        self.screen.add_selector(self.tracker, OBJECT)
        self._frame_interval.value = 1 / settings.FPS_PROCESSED
        self._view_model.set_menu_state('all', 'disabled')
        self.state_control.change_state('object selected')
        if run_thread_after is not None:
            run_thread_after().start()

    def _calibrate_common(self, name):
        if self.selecting.selecting_is_done(AREA):
            self.previous_area = self.screen.get_selector(AREA)
            self.screen.remove_selector(AREA)

        calibrator = self.calibrators[name]

        calibrator.start()
        self._view_model.new_selection(OBJECT, reselect_while_calibrating=True,
                                       additional_callback=calibrator.calibrate)
        self._view_model.progress_bar_set_visibility(True)
        self._view_model.set_progress(0)

    def calibrate_noise_threshold(self):
        self._calibrate_common('noise threshold')

    def calibrate_coordinate_system(self):
        self._calibrate_common('coordinate system')

    def calibrate_laser(self):
        self.laser.calibrate_laser()
        self.state_control.change_state('laser calibrated')

    def center_laser(self):
        self.laser.center_laser()

    def move_laser(self, x, y):
        self.laser.move_laser(x, y)

    def _active_process_in_progress(self):
        is_calibrating = self._calibrating_in_progress()
        is_selecting_in_progress = self.selecting.selecting_in_progress(AREA) or \
                                   self.selecting.selecting_in_progress(OBJECT)
        is_active_process = is_selecting_in_progress or self.tracker.in_progress or is_calibrating
        return is_active_process

    def cancel_active_process(self, need_confirm=True):
        is_calibrating = self._calibrating_in_progress()
        is_selecting_in_progress = self.selecting.selecting_in_progress(AREA) or \
                                   self.selecting.selecting_in_progress(OBJECT)
        is_active_process = is_selecting_in_progress or self.tracker.in_progress or is_calibrating
        if not is_active_process:
            return
        if need_confirm:
            if is_active_process:
                need_confirm = view_output.ask_confirmation('Прервать активный процесс?')
                if not need_confirm:
                    return
        if self.tracker.in_progress:
            self.screen.remove_selector(OBJECT)
        self.selecting.cancel()
        cancel_all_calibrators = [i.cancel() for i in self.calibrators.values()]
        self._frame_interval.value = 1 / settings.FPS_VIEWED
        if is_calibrating:
            self.try_restore_previous_area()
        Processor.load_color()  # Если вышло за границу и отменили, то остаётся красный цвет
        self._view_model.set_menu_state('all', 'normal')

    def rotate_image(self, degree, user_action=True):
        if private_settings.ROTATION_ANGLE == degree and user_action:
            return

        if self.selecting.selecting_is_done(AREA):
            confirm = view_output.ask_confirmation('Выделенная область будет стёрта. Продолжить?')
            if not confirm:
                return

        private_settings.ROTATION_ANGLE = degree
        self.screen.remove_selector(AREA)
        self.previous_area = None
        self.camera.set_frame_rotate(degree)
        if degree in (90, 270):
            self._view_model.setup_window_geometry(reverse=True)
        else:
            self._view_model.setup_window_geometry(reverse=False)
        self._view_model.set_rotate_angle(degree)
        if user_action:
            self.state_control.change_state('coordinate system changed')

    def flip_image(self, side, user_action=True):
        if private_settings.FLIP_SIDE == side and user_action:
            return

        if self.selecting.selecting_is_done(AREA):
            confirm = view_output.ask_confirmation('Выделенная область будет стёрта. Продолжить?')
            if not confirm:
                return

        private_settings.FLIP_SIDE = side
        self.screen.remove_selector(AREA)
        self.previous_area = None
        self.camera.set_frame_flip(side)
        self._view_model.set_flip_side(side)
        if user_action:
            self.state_control.change_state('coordinate system changed')

    def stop_thread(self):
        cancel_all_calibrators = [i.cancel() for i in self.calibrators.values()]
        self.laser.center_laser()
        self.laser.stop_thread()
        super(Orchestrator, self).stop_thread()
