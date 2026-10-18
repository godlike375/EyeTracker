from PySide6.QtWidgets import QMainWindow, QFileDialog, QLabel, QProgressBar, QStatusBar
from PySide6.QtCore import QTimer, Qt, Signal
from pathlib import Path

from tracker.camera import VideoAdapter
from model.pupil_pipeline import PupilPipeline
from tracker.utils.shared_objects import SharedBox, INITIAL_VALUE
from tracker.utils.coordinates import Point
from tracker.utils.threading import StoppableThread
from tracker.utils.error_handler import ErrorHandler
from tracker.utils.state_machine import StateMachine
from model.interfaces import StatusMessage
from model.laser_controller import LaserController, LaserConfig
from model.virtual_laser_controller import VirtualLaserController
from model.area_controller import AreaController
from model.calibration_controller import CalibrationController
from view.gl_widget import OpenGLVideoWidget
from view.settings_dialog import SettingsDialog
from view.toast import ToastManager
from view.log_panel import LogPanel
from view import i18n
from view.i18n import tr
from new_settings import AppSettings

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
DEFAULT_YOLO_MODEL = str(MODELS_DIR / "pupil_seg_best.pt")


class MainWindow(QMainWindow):
    notification = Signal(str, str)
    error_occurred = Signal(str)
    warning_occurred = Signal(str)
    calibration_progress = Signal(int)
    calibration_finished = Signal(bool)
    calibration_point = Signal(int, int, int)

    def __init__(self, adapter: VideoAdapter, stop_event, source_queue, roi_array):
        super().__init__()
        self.adapter = adapter
        self.stop_event = stop_event
        self.source_queue = source_queue
        self.roi_array = roi_array
        self.detector = None
        self.last_roi = None

        self.setWindowTitle(tr('app.title'))
        self.gl_widget = OpenGLVideoWidget(adapter, self, roi_array, self)
        self.setCentralWidget(self.gl_widget)
        self.resize(adapter.width, adapter.height)
        self.toast = ToastManager(self, self.gl_widget)
        self.log_panel = LogPanel(self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_panel)
        self.log_panel.hide()
        self.error_handler = ErrorHandler(
            on_fatal_error=lambda message: self.show_error(message),
            auto_restart_delay=0,
            max_consecutive_errors=10_000,
        )

        self.settings = AppSettings({
            "render_fps": {"value": 30, "min": 1, "max": 144},
            "rotate_degree": {"value": 0, "min": 0, "max": 270},
            "camera_id": {"value": 0, "min": 0, "max": 10},
            "target_fps": {"value": 120, "min": 15, "max": 240},
            "detector_fps": {"value": 60, "min": 15, "max": 120},
            "eyes_count": {"value": 1, "min": 1, "max": 2},
            "averaging_frames_count": {"value": 2, "min": 1, "max": 10},
            "serial_port": {"value": 1, "min": 0, "max": 20},
            "baud_rate": {"value": 19200, "min": 9600, "max": 115200},
            "stable_position_duration": {"value": 0.67, "min": 0.1, "max": 2.0},
            "max_laser_range": {"value": 6000, "min": 1000, "max": 10000},
            "downscale_factor": {"value": 0.5, "min": 0.1, "max": 1.0},
            "noise_threshold_range": {"value": 0.0, "min": 0.0, "max": 10.0},
            "threshold_calibration_duration": {"value": 4, "min": 1, "max": 16},
            "same_frames_threshold": {"value": 0.85, "min": 0.01, "max": 0.99},
            "paint_color_r": {"value": 0, "min": 0, "max": 255},
            "paint_color_g": {"value": 255, "min": 0, "max": 255},
            "paint_color_b": {"value": 0, "min": 0, "max": 255},
            "laser_debug": False,
            "virtual_laser": {"value": True},
            "virtual_laser_speed": {"value": 6000, "min": 100, "max": 200000},
            "language": i18n.DEFAULT_LANGUAGE,
            "use_haar": {"value": True},
            "use_yolo": {"value": True},
            "use_dark_area": {"value": False},
            "yolo_model_path": {"value": DEFAULT_YOLO_MODEL},
            "yolo_conf": {"value": 0.25, "min": 0.0, "max": 1.0},
            "yolo_imgsz": {"value": 192, "min": 64, "max": 640},
            "track_after_yolo": {"value": True},
            "yolo_track_frames": {"value": 10, "min": 1, "max": 120},
        })
        i18n.set_language(self.settings.language)
        self._tracking_running = False
        self._calibrating = False

        self._setup_status_bar()
        self._setup_progress_bar()
        self._create_menu()
        self._setup_laser()

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_detector)
        self.update_timer.start(16)

        self.gl_widget.timer.start(1000 // self.settings.render_fps)

    def _setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel(tr('status.initializing'))
        self.status_bar.addWidget(self.status_label)
        self.fps_label = QLabel("FPS: --")
        self.status_bar.addPermanentWidget(self.fps_label)

    def _setup_progress_bar(self):
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _rebuild_menu(self):
        bar = self.menuBar()
        bar.clear()
        self._create_menu()

    def _create_menu(self):
        bar = self.menuBar()

        file_menu = bar.addMenu(tr('menu.file'))
        file_menu.addAction(tr('file.open_video'), self._open_file)
        file_menu.addAction(tr('file.use_camera'), self._open_camera)
        file_menu.addSeparator()
        file_menu.addAction(tr('file.settings'), self._show_settings)
        file_menu.addSeparator()
        file_menu.addAction(tr('file.exit'), self.close)

        calibration_menu = bar.addMenu(tr('menu.calibration'))
        calibration_menu.addAction(tr('calib.initialize_laser'), self._calibrate_laser)
        calibration_menu.addAction(tr('calib.coordinates_auto'), self._run_auto_calibration)
        calibration_menu.addAction(tr('calib.cancel'), self._cancel_calibration)
        calibration_menu.addSeparator()
        calibration_menu.addAction(tr('calib.set_area_manual'), self._begin_manual_area)
        calibration_menu.addAction(tr('calib.cancel_area'), self._cancel_manual_area)
        calibration_menu.addSeparator()
        calibration_menu.addAction(tr('calib.reset'), self._reset_calibration)

        manual_menu = bar.addMenu(tr('menu.manual'))
        manual_menu.addAction(tr('manual.center_laser'), self._center_laser)
        manual_menu.addSeparator()
        manual_menu.addAction(tr('manual.top_left'), lambda: self._move_laser(0))
        manual_menu.addAction(tr('manual.top_right'), lambda: self._move_laser(1))
        manual_menu.addAction(tr('manual.bottom_right'), lambda: self._move_laser(2))
        manual_menu.addAction(tr('manual.bottom_left'), lambda: self._move_laser(3))

        tracking_menu = bar.addMenu(tr('menu.tracking'))
        self.start_tracking_action = tracking_menu.addAction(tr('tracking.start'), self._start_tracking)
        self.stop_tracking_action = tracking_menu.addAction(tr('tracking.stop'), self._stop_tracking)
        self.start_tracking_action.setEnabled(False)
        self.stop_tracking_action.setEnabled(self._tracking_running)

        view_menu = bar.addMenu(tr('menu.view'))
        view_menu.addAction(tr('view.rotate0'), lambda: self._rotate(0))
        view_menu.addAction(tr('view.rotate90'), lambda: self._rotate(90))
        view_menu.addAction(tr('view.rotate180'), lambda: self._rotate(180))
        view_menu.addAction(tr('view.rotate270'), lambda: self._rotate(270))
        view_menu.addSeparator()
        view_menu.addAction(tr('view.flip_h'), self._flip_horizontal)
        view_menu.addAction(tr('view.flip_v'), self._flip_vertical)
        view_menu.addSeparator()
        self.log_panel_action = view_menu.addAction(tr('view.show_log'))
        self.log_panel_action.setCheckable(True)
        self.log_panel_action.setChecked(self.log_panel.isVisible())
        self.log_panel_action.toggled.connect(self._toggle_log_panel)

        language_menu = bar.addMenu(tr('menu.language'))
        current = i18n.get_language()
        english_action = language_menu.addAction(tr('lang.english'), lambda: self._set_language('en'))
        english_action.setCheckable(True)
        english_action.setChecked(current == 'en')
        russian_action = language_menu.addAction(tr('lang.russian'), lambda: self._set_language('ru'))
        russian_action.setCheckable(True)
        russian_action.setChecked(current == 'ru')

    def _set_language(self, language: str):
        if language == i18n.get_language():
            self._rebuild_menu()
            return
        i18n.set_language(language)
        self.settings.language = language
        self.setWindowTitle(tr('app.title'))
        self._rebuild_menu()
        name = tr('lang.russian') if language == 'ru' else tr('lang.english')
        self._update_status(tr('lang.switched', name=name))

    def _toggle_log_panel(self, checked: bool):
        self.log_panel.setVisible(checked)

    def _setup_laser(self):
        self.notification.connect(self._on_notification)
        self.error_occurred.connect(self._on_error)
        self.warning_occurred.connect(self._on_warning)
        self.calibration_progress.connect(self.set_progress)
        self.calibration_finished.connect(self._on_calibration_finished)
        self.calibration_point.connect(self._on_calibration_point)
        self._calibration_thread = None
        self._laser_config = LaserConfig.from_settings(self.settings)
        self._laser_debug = self.settings.laser_debug
        self._virtual_laser = bool(self.settings.virtual_laser)
        self.laser = self._make_laser_controller(self._laser_config, self._laser_debug)
        self.area = AreaController(
            min_xy=-self.settings.max_laser_range,
            max_xy=self.settings.max_laser_range,
        )
        self.calibration = CalibrationController(
            laser=self.laser,
            area=self.area,
            video_adapter=self.adapter,
            notifier=self,
            spot_provider=self._spot_provider(),
            on_corner=lambda index, point: self.calibration_point.emit(index, int(point.x), int(point.y)),
        )
        self.state_control = StateMachine([
            ('laser connected', False, 'Connect the laser'),
            ('area calibrated', False, 'Calibrate the coordinate system'),
            ('tracking', False, 'Ready to track'),
        ], on_state_changed=lambda tip: self._update_status(tip) if tip else None)
        if self.laser.is_initialized:
            self.laser.start()
        self.state_control.change_state('laser connected', self.laser.is_initialized)

    def _make_laser_controller(self, config: LaserConfig, debug: bool):
        if self.settings.virtual_laser:
            controller = VirtualLaserController(
                notifier=self, config=config, speed=self.settings.virtual_laser_speed)
            controller.set_frame_size(self.adapter.width, self.adapter.height)
            return controller
        return LaserController(notifier=self, config=config, debug_on=debug)

    def _spot_provider(self):
        if self.settings.virtual_laser and hasattr(self.laser, 'current_screen_point'):
            return self.laser.current_screen_point
        return None

    def _restart_laser(self):
        if not hasattr(self, "laser"):
            return
        new_config = LaserConfig.from_settings(self.settings)
        new_debug = self.settings.laser_debug
        new_virtual = bool(self.settings.virtual_laser)
        if (new_config == self._laser_config and new_debug == self._laser_debug
                and new_virtual == self._virtual_laser):
            return
        self._laser_config = new_config
        self._laser_debug = new_debug
        self._virtual_laser = new_virtual
        self.laser.stop()
        self.laser = self._make_laser_controller(new_config, new_debug)
        self.area = AreaController(
            min_xy=-self.settings.max_laser_range,
            max_xy=self.settings.max_laser_range,
        )
        self.calibration = CalibrationController(
            laser=self.laser,
            area=self.area,
            video_adapter=self.adapter,
            notifier=self,
            spot_provider=self._spot_provider(),
            on_corner=lambda index, point: self.calibration_point.emit(index, int(point.x), int(point.y)),
        )
        if self.laser.is_initialized:
            self.laser.start()
        if hasattr(self, "state_control"):
            self.state_control.change_state('laser connected', self.laser.is_initialized)

    def _apply_laser_speed(self):
        if hasattr(self.laser, "set_speed"):
            self.laser.set_speed(self.settings.virtual_laser_speed)

    def notify(self, message: str, level: StatusMessage = StatusMessage.INFO):
        self.notification.emit(message, level.value)

    def show_error(self, message: str):
        self.error_occurred.emit(message)

    def show_warning(self, message: str):
        self.warning_occurred.emit(message)

    def is_virtual_laser(self) -> bool:
        return bool(getattr(self, "_virtual_laser", self.settings.virtual_laser))

    def laser_screen_point(self):
        if not hasattr(self, "laser"):
            return None
        if (not self._calibrating) and hasattr(self, "area") and self.area.is_set:
            point = self.area.calc_screen_coords(self.laser.current_position)
            if point is not None:
                return point
        if self.is_virtual_laser() and hasattr(self.laser, "current_screen_point"):
            return self.laser.current_screen_point()
        return None

    def _on_notification(self, message: str, level: str):
        self._update_status(message)
        self.toast.show_message(message, level)

    def _on_error(self, message: str):
        self._update_status(f"[ERROR] {message}")
        self.toast.show_message(message, StatusMessage.ERROR)

    def _on_warning(self, message: str):
        self._update_status(f"[WARNING] {message}")
        self.toast.show_message(message, StatusMessage.WARNING)

    def _update_status(self, message: str):
        self.status_label.setText(message)

    def _make_detector(self, eye_area):
        return PupilPipeline(
            eyes_count=self.settings.eyes_count,
            averaging_frames_count=self.settings.averaging_frames_count,
            detect_area=eye_area,
            video_adapter=self.adapter,
            target_fps=self.settings.detector_fps,
            use_haar=self.settings.use_haar,
            use_yolo=self.settings.use_yolo,
            use_dark_area=self.settings.use_dark_area,
            yolo_model_path=self.settings.yolo_model_path,
            yolo_conf=self.settings.yolo_conf,
            yolo_imgsz=self.settings.yolo_imgsz,
            track_after_yolo=self.settings.track_after_yolo,
            yolo_track_frames=self.settings.yolo_track_frames,
            downscale_factor=self.settings.downscale_factor,
            noise_threshold=self.settings.noise_threshold_range,
        )

    def _update_detector(self):
        current_roi = list(self.roi_array)
        if self.detector is None or current_roi != self.last_roi:
            if self.detector:
                self.detector.stop_process()
            eye_area = SharedBox('i', INITIAL_VALUE)
            eye_area.left_top.x, eye_area.left_top.y = current_roi[0], current_roi[1]
            eye_area.right_bottom.x, eye_area.right_bottom.y = current_roi[2], current_roi[3]
            self.detector = self._make_detector(eye_area)
            self.detector.start_process()
            self.last_roi = current_roi
            self._update_status(f"Tracking eye region: {current_roi}")
        self._tracking_step()

    def _tracking_step(self):
        if not self._tracking_running:
            return
        if self.detector is None:
            return
        pupil = self.detector.pupil_detector.pupil
        if pupil is None or not pupil.is_valid:
            return
        if not self.area.is_set:
            return
        laser_coords = self.area.calc_laser_coords(Point(pupil.x, pupil.y))
        if hasattr(self.laser, "track_position"):
            self.laser.track_position(laser_coords)
        else:
            self.laser.set_new_position(laser_coords)

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Video")
        if path:
            self.source_queue.put(path)
            self._update_status(tr('status.opened_video', path=path))

    def _open_camera(self):
        self.source_queue.put(None)
        self._update_status(tr('status.using_camera'))

    SETTINGS_SECTIONS = [
        ("set.section.video", [
            ("render_fps", "set.render_fps"),
            ("rotate_degree", "set.rotate_degree"),
            ("camera_id", "set.camera_id"),
            ("target_fps", "set.target_fps"),
        ]),
        ("set.section.detection", [
            ("detector_fps", "set.detector_fps"),
            ("eyes_count", "set.eyes_count"),
            ("averaging_frames_count", "set.averaging_frames_count"),
            ("use_haar", "set.use_haar"),
            ("use_yolo", "set.use_yolo"),
            ("use_dark_area", "set.use_dark_area"),
            ("yolo_model_path", "set.yolo_model_path"),
            ("yolo_conf", "set.yolo_conf"),
            ("yolo_imgsz", "set.yolo_imgsz"),
            ("track_after_yolo", "set.track_after_yolo"),
            ("yolo_track_frames", "set.yolo_track_frames"),
        ]),
        ("set.section.tracking", [
            ("downscale_factor", "set.downscale_factor"),
            ("noise_threshold_range", "set.noise_threshold_range"),
            ("threshold_calibration_duration", "set.threshold_calibration_duration"),
            ("same_frames_threshold", "set.same_frames_threshold"),
        ]),
        ("set.section.laser", [
            ("serial_port", "set.serial_port"),
            ("baud_rate", "set.baud_rate"),
            ("stable_position_duration", "set.stable_position_duration"),
            ("max_laser_range", "set.max_laser_range"),
            ("laser_debug", "set.laser_debug"),
            ("virtual_laser", "set.virtual_laser"),
            ("virtual_laser_speed", "set.virtual_laser_speed"),
        ]),
        ("set.section.overlay", [
            ("paint_color_r", "set.paint_color_r"),
            ("paint_color_g", "set.paint_color_g"),
            ("paint_color_b", "set.paint_color_b"),
            ("language", "set.language"),
        ]),
    ]

    def _show_settings(self):
        sections = [
            (tr(title_key), [(name, tr(label_key)) for name, label_key in fields])
            for title_key, fields in self.SETTINGS_SECTIONS
        ]
        all_fields = [f for _, fields in self.SETTINGS_SECTIONS for f in fields]
        tooltips = {name: tr(f'tip.{name}') for name, _ in all_fields}
        if SettingsDialog(self.settings, tooltips=tooltips, parent=self, sections=sections).exec():
            self.gl_widget.timer.setInterval(1000 // self.settings.render_fps)
            self.adapter.rotate_degree.value = self.settings.rotate_degree
            self.gl_widget.set_rotate_degree(self.settings.rotate_degree)
            self._restart_laser()
            self._apply_laser_speed()
            self.last_roi = None
            self._update_status(tr('status.settings_updated'))

    def _calibrate_laser(self):
        if not self.laser.is_initialized:
            self.notify(tr('status.laser_not_connected'), StatusMessage.WARNING)
            return
        self._update_status(tr('status.initializing_laser'))
        self.laser.calibrate_laser()

    def _center_laser(self):
        if not self.laser.is_initialized:
            self.notify(tr('status.laser_not_connected'), StatusMessage.WARNING)
            return
        self._update_status(tr('status.centering_laser'))
        self.laser.center_laser()

    def _move_laser(self, corner_index: int):
        if not 0 <= corner_index < len(self.laser.laser_borders):
            return
        if not self.laser.is_initialized:
            self.notify(tr('status.laser_not_connected'), StatusMessage.WARNING)
            return
        target = self.laser.laser_borders[corner_index]
        self._update_status(tr('status.moving_laser', pos=target.to_tuple()))
        self.laser.set_new_position(target)

    def _run_auto_calibration(self):
        if not self.laser.is_initialized:
            self.notify(tr('status.laser_not_connected'), StatusMessage.WARNING)
            return
        if self._calibration_thread is not None and self._calibration_thread.is_alive():
            self.notify(tr('status.calibration_running'), StatusMessage.WARNING)
            return
        self.show_progress(True)
        self.set_progress(0)
        self._calibrating = True
        self.gl_widget.clear_calibration_display()
        self._update_status(tr('status.auto_detecting'))
        self._calibration_thread = StoppableThread(target=self._calibration_worker, daemon=True)
        self._calibration_thread.start()

    def _calibration_worker(self):
        self.error_handler.handle_exceptions(self._do_auto_calibration)()

    def _do_auto_calibration(self):
        ok = self.calibration.calibrate(
            on_progress=lambda value: self.calibration_progress.emit(value)
        )
        self.calibration_finished.emit(ok)

    def _cancel_calibration(self):
        self.calibration.cancel()
        if self._calibration_thread is not None:
            self._calibration_thread.stop()
        self._calibrating = False
        self.show_progress(False)
        self.set_progress(0)
        self._update_status(tr('status.calibration_cancelled'))

    def _on_calibration_point(self, index, x, y):
        self.gl_widget.set_calibration_preview_point(index, x, y)

    def _on_calibration_finished(self, ok: bool):
        self.show_progress(False)
        self.set_progress(0)
        self._calibrating = False
        self._update_status(tr('status.calibration_complete') if ok else tr('status.calibration_failed'))
        if ok:
            self.state_control.change_state('area calibrated')
            self.notify(tr('status.coordinate_calibrated'), StatusMessage.INFO)
        else:
            self.gl_widget.clear_calibration_display()
        self._update_tracking_availability()

    def _begin_manual_area(self):
        self._update_status(tr('status.click_area'))
        self.gl_widget.clear_calibration_display()
        self.gl_widget.begin_area_selection()

    def _cancel_manual_area(self):
        self.gl_widget.cancel_area_selection()
        self._update_status(tr('status.area_cancelled'))

    def on_area_points_selected(self, points):
        if len(points) != 4:
            self.notify(tr('status.area_requires_4'), StatusMessage.WARNING)
            return
        try:
            self.area.set_area(list(points), self.laser.laser_borders)
        except ValueError as exc:
            self.notify(tr('status.invalid_area', error=exc), StatusMessage.ERROR)
            return
        self._update_status(tr('status.area_calibrated_manual'))
        self.state_control.change_state('area calibrated')
        self.notify(tr('status.area_calibrated'), StatusMessage.INFO)

    def _reset_calibration(self):
        self.area.clear()
        self.gl_widget.clear_calibration_display()
        if hasattr(self, "state_control"):
            self.state_control.change_state('area calibrated', False)
        self._update_status(tr('status.calibration_reset'))
        self._update_tracking_availability()

    def _start_tracking(self):
        self._tracking_running = True
        self._update_status(tr('status.tracking_started'))
        self._update_tracking_availability()

    def _stop_tracking(self):
        self._tracking_running = False
        self._update_status(tr('status.tracking_stopped'))
        self._update_tracking_availability()

    def _update_tracking_availability(self):
        if not hasattr(self, 'start_tracking_action'):
            return
        roi_set = len(self.roi_array) >= 4 and self.roi_array[2] > 0
        self.start_tracking_action.setEnabled(roi_set and not self._tracking_running)
        self.stop_tracking_action.setEnabled(self._tracking_running)

    def on_roi_selected(self):
        self._update_tracking_availability()

    def _rotate(self, degree: int):
        self.settings.rotate_degree = degree
        self.adapter.rotate_degree.value = degree
        self.gl_widget.set_rotate_degree(degree)
        width, height = self.gl_widget.target_resolution
        self.resize(width, height)
        self._update_status(tr('status.rotated', degree=degree))

    def _flip_horizontal(self):
        self.adapter.flip_horizontal = not self.adapter.flip_horizontal
        self.gl_widget.update()
        self._update_status(tr('status.flipped_h'))

    def _flip_vertical(self):
        self.adapter.flip_vertical = not self.adapter.flip_vertical
        self.gl_widget.update()
        self._update_status(tr('status.flipped_v'))

    def set_progress(self, value: int):
        self.progress_bar.setValue(value)

    def show_progress(self, visible: bool):
        self.progress_bar.setVisible(visible)

    def closeEvent(self, e):
        if hasattr(self, "calibration"):
            self.calibration.cancel()
        if self._calibration_thread is not None:
            self._calibration_thread.stop()
        if self.laser:
            self.laser.stop()
        if self.detector:
            self.detector.stop_process()
        self.stop_event.set()
        super().closeEvent(e)
