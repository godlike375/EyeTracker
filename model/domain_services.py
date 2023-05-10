import sys
from time import time, sleep

from common.logger import logger
from common.program import exit_program
from common.settings import settings, OBJECT, AREA, private_settings
from common.thread_helpers import ThreadLoopable, MutableValue
from model.area_controller import AreaController
from model.camera_extractor import CameraService
from model.frame_processing import Tracker, NoiseThresholdCalibrator, CoordinateSystemCalibrator
from model.other_services import SelectingService, LaserService, StateMachine, OnScreenService
from view import view_output
from view.drawing import Processor
from view.view_model import ViewModel

RESTART_IN_TIME_SEC = 10


# WARNING: Пробовал увеличивать количество потоков в программе до 4-х (+ экстрактор + трекер в своих потоках)
#  Итог: это только ухудшило производительность, так что больше 2-х потоков смысла иметь нет
#  И запускать из цикла отрисовки вьюхи тоже смысла нет, т.к. это асинхронный цикл и будет всё тормозить


class Orchestrator(ThreadLoopable):

    def __init__(self, view_model: ViewModel, run_immediately: bool = True, area: tuple = None, debug_on=False):
        self._view_model = view_model
        self.camera = CameraService(settings.CAMERA_ID)
        self.area_controller = AreaController(min_xy=-settings.MAX_LASER_RANGE_PLUS_MINUS,
                                              max_xy=settings.MAX_LASER_RANGE_PLUS_MINUS)
        self.tracker = Tracker(settings.MEAN_COORDINATES_FRAME_COUNT)
        self.state_control = StateMachine(self._view_model)
        self.screen = OnScreenService(self)
        self.selecting = SelectingService(self._on_area_selected, self._on_object_selected, self, self.screen)
        self.laser = LaserService(self.state_control, debug_on=debug_on)

        self._current_frame = None

        self.calibrators = {'noise threshold': NoiseThresholdCalibrator(self, self._view_model),
                            'coordinate system': CoordinateSystemCalibrator(self, self._view_model)}

        self.previous_area = None
        self._throttle_to_fps_viewed = time()
        self._frame_interval = MutableValue(1 / settings.FPS_VIEWED)
        self._fatal_error_count_repeatedly = 0
        self.rotate_image(private_settings.ROTATION_ANGLE, user_action=False)
        self.flip_image(private_settings.FLIP_SIDE, user_action=False)
        if self.camera.initialized:
            self.state_control.change_tip('camera connected')
        if self.laser.initialized:
            self.state_control.change_tip('laser connected')
        if area is not None:
            self.selecting.load_selected_area(area)

        # self.calibrate_laser()
        # TODO: FIXME почему-то вызывается, но калибровки не происходит

        super().__init__(self._processing_loop, self._frame_interval, run_immediately)

    def _processing_loop(self):
        try:
            frame = self.camera.extract_frame()
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
        else:
            self._fatal_error_count_repeatedly = 0

    def _handle_fatal_error(self):
        self._fatal_error_count_repeatedly += 1
        if self._fatal_error_count_repeatedly > 2:
            view_output.show_error(f'В связи с множественными внутренними ошибками подключения и синхронизации '
                                   f' работа программы не может быть продолжена.'
                                   f' Программа перезапустится автоматически через {RESTART_IN_TIME_SEC} секунд')
            for i in range(RESTART_IN_TIME_SEC, 0, -1):
                sleep(1)
                self._view_model.set_tip(f'Перезапуск программы будет произведён через {i} секунд')
            self._view_model.execute_command(sys.exit)
            exit_program(self, restart=True)

    def _calibrating_in_progress(self):
        return any([i.in_progress for i in self.calibrators.values()])

    def _tracking(self, frame):
        center = self.tracker.get_tracked_position(frame)
        if self._calibrating_in_progress():
            return
        object_relative_coords = self._move_to_relative_cords(center)
        if object_relative_coords is not None:
            self._view_model.set_tip(f'Текущие координаты объекта: '
                                     f'{object_relative_coords.x, object_relative_coords.y}')

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
        result = self.laser.set_new_position(relative_coords)
        if result is not None:
            return relative_coords
        self.cancel_active_process(need_confirm=False)

    def _on_area_selected(self):
        selected, area = self.selecting.check_selected_correctly(AREA)
        if not selected:
            # TODO: если не выделялась вручную, то retry не нужен. Калибровку надо перезапускать
            self._view_model.new_selection(AREA, retry_select_object_in_calibrating=True)
            return
        self._view_model.set_menu_state('all', 'normal')
        self.previous_area = area
        self.area_controller.set_area(area, self.laser.laser_borders)
        self.state_control.change_tip('coordinate system calibrated')

    def _on_object_selected(self, run_thread_after=None):
        selected, object = self.selecting.check_selected_correctly(OBJECT)
        out_of_area = False
        if selected and not (self._calibrating_in_progress()):
            out_of_area = self.area_controller.point_is_out_of_area(object.center)
            if out_of_area:
                view_output.show_error('Невозможно выделить объект за границами области слежения.')
                self.screen.remove_selector(OBJECT)

        if not selected or out_of_area:
            self._view_model.new_selection(OBJECT, retry_select_object_in_calibrating=True,
                                           additional_callback=run_thread_after)
            return

        self.tracker.start_tracking(self._current_frame, object.left_top, object.right_bottom)
        self.screen.add_selector(self.tracker, OBJECT)
        self._frame_interval.value = 1 / settings.FPS_PROCESSED
        self._view_model.set_menu_state('all', 'disabled')
        self.state_control.change_tip('object selected')
        if run_thread_after is not None:
            run_thread_after().start()

    def _new_object(self, select_in_calibrating):
        if select_in_calibrating:
            return True

        if self.laser.errored:
            view_output.show_error(
                'Необходимо откалибровать контроллер лазера повторно. '
                'До этого момента слежение за объектом невозможно.')
            self.state_control.change_tip('laser calibrated', False)
            return False
        if self.selecting.selecting_is_done(OBJECT):
            confirm = view_output.ask_confirmation('Выделенный объект перестанет отслеживаться. Продолжить?')
            if not confirm:
                return False

        return True

    def _new_area(self, dont_reselect_area):
        # TODO: поправить логику и сделать без костылей вроде этого
        if dont_reselect_area:
            return False

        tracking_stop_question = ''
        if self.selecting.selecting_is_done(OBJECT):
            tracking_stop_question = 'Слежение за целью будет остановлено. '
        if self.selecting.selecting_is_done(AREA):
            confirm = view_output.ask_confirmation(f'{tracking_stop_question}'
                                                   f'Выделенная область будет стёрта. Продолжить?')
            if not confirm:
                return False
        self.screen.remove_selector(OBJECT)
        return True

    def new_selection(self, name, retry_select_object_in_calibrating=False, additional_callback=None):

        if OBJECT in name:
            if not self._new_object(retry_select_object_in_calibrating):
                return

        if AREA in name:
            if not self._new_area(dont_reselect_area=retry_select_object_in_calibrating):
                return

        self.screen.remove_selector(name)
        self._view_model.set_menu_state('all', 'disabled')
        return self.selecting.create_selector(name, additional_callback)

    def _calibrate_common(self, name):
        if self.selecting.selecting_is_done(AREA):
            self.previous_area = self.screen.get_selector(AREA)
            self.screen.remove_selector(AREA)

        calibrator = self.calibrators[name]

        calibrator.start()
        self._view_model.set_menu_state('all', 'disabled')
        self._view_model.new_selection(OBJECT, retry_select_object_in_calibrating=True,
                                       additional_callback=calibrator.calibrate)
        self._view_model.progress_bar_set_visibility(True)
        self._view_model.set_progress(0)

    def calibrate_noise_threshold(self):
        self._calibrate_common('noise threshold')

    def calibrate_coordinate_system(self):
        self._calibrate_common('coordinate system')

    def calibrate_laser(self):
        self.laser.calibrate_laser()
        self.state_control.change_tip('laser calibrated')

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
        [i.cancel() for i in self.calibrators.values()]
        self._frame_interval.value = 1 / settings.FPS_VIEWED
        if is_calibrating:
            self.try_restore_previous_area()
        Processor.load_color() # Если вышло за границу и отменили, то остаётся красный цвет

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
        self.state_control.change_tip('coordinate system changed')

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
        self.state_control.change_tip('coordinate system changed')

    def stop_thread(self):
        [i.cancel() for i in self.calibrators.values()]
        super(Orchestrator, self).stop_thread()
