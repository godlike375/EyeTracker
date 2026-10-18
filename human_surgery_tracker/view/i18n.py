"""Простая локализация интерфейса (RU/EN).

Использование:
    from view.i18n import tr, set_language, get_language, LANGUAGES
    set_language('ru')
    tr('menu.file')            # -> '&Файл'
    tr('status.rotated', degree=90)
"""

from typing import Dict, Optional

LANGUAGES = ('ru', 'en')
DEFAULT_LANGUAGE = 'ru'

_current_language = DEFAULT_LANGUAGE

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    'app.title': {
        'en': 'Human Surgery Tracker',
        'ru': 'Трекер для хирургии глаза',
    },

    # --- menus ---
    'menu.file': {'en': '&File', 'ru': '&Файл'},
    'menu.calibration': {'en': '&Calibration', 'ru': '&Калибровка'},
    'menu.manual': {'en': '&Manual', 'ru': '&Ручное управление'},
    'menu.tracking': {'en': '&Tracking', 'ru': '&Слежение'},
    'menu.view': {'en': '&View', 'ru': '&Вид'},
    'menu.language': {'en': '&Language', 'ru': '&Язык'},

    # --- file ---
    'file.open_video': {'en': '&Open Video', 'ru': '&Открыть видео'},
    'file.use_camera': {'en': '&Use Camera', 'ru': 'Включить &камеру'},
    'file.settings': {'en': '&Settings', 'ru': '&Настройки'},
    'file.exit': {'en': '&Exit', 'ru': 'В&ыход'},

    # --- calibration ---
    'calib.initialize_laser': {'en': '&Initialize Laser', 'ru': '&Инициализация лазера'},
    'calib.coordinates_auto': {'en': 'Calibrate &Coordinates (Auto)', 'ru': 'Калибровка &координат (авто)'},
    'calib.cancel': {'en': '&Cancel Calibration', 'ru': '&Отменить калибровку'},
    'calib.set_area_manual': {'en': 'Set Area Manual&ly (4 points)', 'ru': 'Задать область вручн&ую (4 точки)'},
    'calib.cancel_area': {'en': 'Cancel Area Selection', 'ru': 'Отменить выбор области'},
    'calib.reset': {'en': '&Reset Calibration', 'ru': '&Сбросить калибровку'},

    # --- manual ---
    'manual.initialize_laser': {'en': '&Initialize Laser', 'ru': '&Инициализация лазера'},
    'manual.center_laser': {'en': '&Center Laser', 'ru': 'Центрировать &лазер'},
    'manual.top_left': {'en': 'Move to &Top-Left', 'ru': 'В &левый верхний угол'},
    'manual.top_right': {'en': 'Move to Top-&Right', 'ru': 'В правый &верхний угол'},
    'manual.bottom_right': {'en': 'Move to &Bottom-Right', 'ru': 'В правый &нижний угол'},
    'manual.bottom_left': {'en': 'Move to Bottom-&Left', 'ru': 'В левый &нижний угол'},

    # --- tracking ---
    'tracking.start': {'en': '&Start Tracking', 'ru': '&Начать слежение'},
    'tracking.stop': {'en': '&Stop Tracking', 'ru': '&Остановить слежение'},

    # --- view ---
    'view.rotate0': {'en': 'Rotate &0°', 'ru': 'Повернуть на &0°'},
    'view.rotate90': {'en': 'Rotate &90°', 'ru': 'Повернуть на &90°'},
    'view.rotate180': {'en': 'Rotate 1&80°', 'ru': 'Повернуть на 1&80°'},
    'view.rotate270': {'en': 'Rotate &270°', 'ru': 'Повернуть на &270°'},
    'view.flip_h': {'en': '&Flip Horizontal', 'ru': 'Отразить &горизонтально'},
    'view.flip_v': {'en': 'Flip &Vertical', 'ru': 'Отразить &вертикально'},
    'view.show_log': {'en': 'Show &Log Panel', 'ru': 'Показать &панель логов'},

    # --- language ---
    'lang.english': {'en': 'English', 'ru': 'English'},
    'lang.russian': {'en': 'Russian', 'ru': 'Русский'},
    'lang.switched': {'en': 'Language: {name}', 'ru': 'Язык: {name}'},

    # --- settings labels ---
    'set.render_fps': {'en': 'Render FPS', 'ru': 'FPS отрисовки'},
    'set.rotate_degree': {'en': 'Rotation', 'ru': 'Поворот'},
    'set.camera_id': {'en': 'Camera ID', 'ru': 'ID камеры'},
    'set.target_fps': {'en': 'Target FPS', 'ru': 'Целевой FPS'},
    'set.detector_fps': {'en': 'Detector FPS', 'ru': 'FPS детектора'},
    'set.eyes_count': {'en': 'Eyes Count', 'ru': 'Кол-во глаз'},
    'set.averaging_frames_count': {'en': 'Averaging Frames', 'ru': 'Кадров усреднения'},
    'set.serial_port': {'en': 'Serial Port', 'ru': 'COM-порт'},
    'set.baud_rate': {'en': 'Baud Rate', 'ru': 'Скорость порта'},
    'set.stable_position_duration': {'en': 'Stable Position (s)', 'ru': 'Стабилизация (с)'},
    'set.max_laser_range': {'en': 'Max Laser Range', 'ru': 'Диапазон лазера'},
    'set.downscale_factor': {'en': 'Downscale Factor', 'ru': 'Масштаб уменьшения'},
    'set.noise_threshold_range': {'en': 'Noise Threshold', 'ru': 'Порог шума'},
    'set.threshold_calibration_duration': {'en': 'Calibration Duration (s)', 'ru': 'Длительность калибровки (с)'},
    'set.same_frames_threshold': {'en': 'Same Frames Threshold', 'ru': 'Порог одинаковых кадров'},
    'set.paint_color_r': {'en': 'Paint Color R', 'ru': 'Цвет наложения R'},
    'set.paint_color_g': {'en': 'Paint Color G', 'ru': 'Цвет наложения G'},
    'set.paint_color_b': {'en': 'Paint Color B', 'ru': 'Цвет наложения B'},
    'set.laser_debug': {'en': 'Laser Debug Mode', 'ru': 'Отладка лазера'},
    'set.virtual_laser': {'en': 'Virtual Laser', 'ru': 'Виртуальный лазер'},
    'set.virtual_laser_speed': {'en': 'Mock Laser Speed', 'ru': 'Скорость mock-лазера'},
    'set.language': {'en': 'Language', 'ru': 'Язык'},
    'set.section.video': {'en': 'Video', 'ru': 'Видео'},
    'set.section.detection': {'en': 'Detection', 'ru': 'Детекция'},
    'set.section.tracking': {'en': 'Tracking', 'ru': 'Слежение'},
    'set.section.laser': {'en': 'Laser', 'ru': 'Лазер'},
    'set.section.overlay': {'en': 'Overlay & Language', 'ru': 'Наложение и язык'},
    'set.use_haar': {'en': 'Haar Eye Search', 'ru': 'Поиск глаза (Haar)'},
    'set.use_yolo': {'en': 'YOLO Pupil Detector', 'ru': 'YOLO-детектор зрачка'},
    'set.use_dark_area': {'en': 'Dark-Area Detector', 'ru': 'Детектор тёмной области'},
    'set.yolo_model_path': {'en': 'YOLO Model Path', 'ru': 'Путь к модели YOLO'},
    'set.yolo_conf': {'en': 'YOLO Confidence', 'ru': 'Порог уверенности YOLO'},
    'set.yolo_imgsz': {'en': 'YOLO Image Size', 'ru': 'Размер входа YOLO'},
    'set.track_after_yolo': {'en': 'Track After YOLO', 'ru': 'Трекать после YOLO'},
    'set.yolo_track_frames': {'en': 'Track Frames (N)', 'ru': 'Кадров трекинга (N)'},

    # --- settings tooltips ---
    'tip.render_fps': {'en': 'Video redraw rate.', 'ru': 'Частота перерисовки видео.'},
    'tip.rotate_degree': {'en': 'Video rotation: 0 / 90 / 180 / 270°.', 'ru': 'Поворот видео: 0 / 90 / 180 / 270°.'},
    'tip.camera_id': {'en': 'Camera device index.', 'ru': 'Индекс устройства камеры.'},
    'tip.target_fps': {'en': 'Target video processing rate.', 'ru': 'Целевая частота обработки видео.'},
    'tip.detector_fps': {'en': 'Eye/pupil detector rate.', 'ru': 'Частота детектора глаз/зрачка.'},
    'tip.eyes_count': {'en': 'Number of tracked eyes (1 or 2).', 'ru': 'Число отслеживаемых глаз (1 или 2).'},
    'tip.averaging_frames_count': {'en': 'Frames averaged for pupil position.', 'ru': 'Кадров усреднения позиции зрачка.'},
    'tip.serial_port': {'en': 'COM port number of the laser controller.', 'ru': 'Номер COM-порта контроллера лазера.'},
    'tip.baud_rate': {'en': 'Serial baud rate.', 'ru': 'Скорость последовательного порта.'},
    'tip.stable_position_duration': {'en': 'Time to wait for the laser to settle, seconds.', 'ru': 'Время ожидания стабилизации лазера, секунды.'},
    'tip.max_laser_range': {'en': 'Laser coordinate range (± value).', 'ru': 'Диапазон координат лазера (± значение).'},
    'tip.downscale_factor': {'en': 'Frame downscale for detection (0.1–1.0).', 'ru': 'Уменьшение кадра для детекции (0.1–1.0).'},
    'tip.noise_threshold_range': {'en': 'Noise rejection threshold while tracking.', 'ru': 'Порог отсечения шума при слежении.'},
    'tip.threshold_calibration_duration': {'en': 'Duration of automatic threshold calibration, seconds.', 'ru': 'Длительность авто-калибровки порога, секунды.'},
    'tip.same_frames_threshold': {'en': 'Similarity threshold to detect static frames.', 'ru': 'Порог схожести для определения статичных кадров.'},
    'tip.paint_color_r': {'en': 'Red component of overlay color.', 'ru': 'Красная составляющая цвета наложения.'},
    'tip.paint_color_g': {'en': 'Green component of overlay color.', 'ru': 'Зелёная составляющая цвета наложения.'},
    'tip.paint_color_b': {'en': 'Blue component of overlay color.', 'ru': 'Синяя составляющая цвета наложения.'},
    'tip.laser_debug': {'en': 'Use a serial stub instead of the real laser.', 'ru': 'Использовать заглушку порта вместо реального лазера.'},
    'tip.virtual_laser': {'en': 'Simulate the laser without hardware; drawn as an orange circle.', 'ru': 'Симуляция лазера без железа; отображается оранжевым кругом.'},
    'tip.virtual_laser_speed': {'en': 'Mock laser movement speed, laser units per second — applies to every movement: calibration, manual moves and tracking (lower = slower/smoother).', 'ru': 'Скорость движения mock-лазера, единиц лазера в секунду — для всех движений: калибровка, ручные перемещения и слежение (меньше — медленнее и плавнее).'},
    'tip.language': {'en': 'Interface language.', 'ru': 'Язык интерфейса.'},
    'tip.use_haar': {'en': 'Haar cascade eye search; if off, YOLO works on the ROI/full frame.', 'ru': 'Поиск глаза каскадом Хаара; если выключено, YOLO работает по ROI/всему кадру.'},
    'tip.use_yolo': {'en': 'Enable YOLO segmentation pupil detector.', 'ru': 'Включить YOLO-сегментацию зрачка.'},
    'tip.use_dark_area': {'en': 'Enable classic dark-area pupil detector (refines inside the YOLO box).', 'ru': 'Включить классический детектор тёмной области (уточняет внутри бокса YOLO).'},
    'tip.yolo_model_path': {'en': 'Path to the YOLO segmentation .pt weights.', 'ru': 'Путь к весам .pt YOLO-сегментации.'},
    'tip.yolo_conf': {'en': 'Minimum detection confidence (0–1).', 'ru': 'Минимальная уверенность детекции (0–1).'},
    'tip.yolo_imgsz': {'en': 'Inference image size for the YOLO model.', 'ru': 'Размер изображения для инференса YOLO.'},
    'tip.track_after_yolo': {'en': 'After a YOLO detection, track its box with dlib instead of running YOLO every frame.', 'ru': 'После детекции YOLO трекать её бокс через dlib вместо запуска YOLO каждый кадр.'},
    'tip.yolo_track_frames': {'en': 'Re-run YOLO every N tracked frames (or earlier if tracking is lost).', 'ru': 'Перезапускать YOLO каждые N кадров трекинга (или раньше при потере слежения).'},

    # --- status / notification messages ---
    'status.initializing': {'en': 'Initializing...', 'ru': 'Инициализация...'},
    'status.rotated': {'en': 'Rotated to {degree} degrees', 'ru': 'Поворот на {degree}°'},
    'status.flipped_h': {'en': 'Flipped horizontally', 'ru': 'Отражено по горизонтали'},
    'status.flipped_v': {'en': 'Flipped vertically', 'ru': 'Отражено по вертикали'},
    'status.settings_updated': {'en': 'Settings updated', 'ru': 'Настройки обновлены'},
    'status.initializing_laser': {'en': 'Initializing laser...', 'ru': 'Инициализация лазера...'},
    'status.calibration_running': {'en': 'Calibration is already running', 'ru': 'Калибровка уже выполняется'},
    'status.calibration_cancelled': {'en': 'Calibration cancelled', 'ru': 'Калибровка отменена'},
    'status.calibration_complete': {'en': 'Calibration complete', 'ru': 'Калибровка завершена'},
    'status.calibration_failed': {'en': 'Calibration failed', 'ru': 'Калибровка не удалась'},
    'status.area_calibrated': {'en': 'Area calibrated', 'ru': 'Область откалибрована'},
    'status.area_calibrated_manual': {'en': 'Area calibrated manually', 'ru': 'Область откалибрована вручную'},
    'status.coordinate_calibrated': {'en': 'Coordinate system calibrated', 'ru': 'Координатная система откалибрована'},
    'status.calibration_reset': {'en': 'Calibration reset', 'ru': 'Калибровка сброшена'},
    'status.laser_not_connected': {'en': 'Laser not connected', 'ru': 'Лазер не подключён'},
    'status.click_area': {
        'en': 'Click 4 area corners in order: TL, TR, BR, BL (arrows to fine-tune, Esc to cancel)',
        'ru': 'Отметьте 4 угла области по порядку: ЛВ, ПВ, ПН, ЛН (стрелки — точная подстройка, Esc — отмена)',
    },
    'status.area_cancelled': {'en': 'Area selection cancelled', 'ru': 'Выбор области отменён'},
    'status.area_requires_4': {'en': 'Area requires exactly 4 points', 'ru': 'Нужно ровно 4 точки области'},
    'status.invalid_area': {'en': 'Invalid area: {error}', 'ru': 'Некорректная область: {error}'},
    'status.tracking_started': {'en': 'Tracking started', 'ru': 'Слежение запущено'},
    'status.tracking_stopped': {'en': 'Tracking stopped', 'ru': 'Слежение остановлено'},
    'status.centering_laser': {'en': 'Centering laser...', 'ru': 'Центрирование лазера...'},
    'status.moving_laser': {'en': 'Moving laser to {pos}', 'ru': 'Движение лазера в {pos}'},
    'status.auto_detecting': {'en': 'Auto-calibration: detecting laser spot...', 'ru': 'Авто-калибровка: поиск пятна лазера...'},
    'status.opened_video': {'en': 'Opened video: {path}', 'ru': 'Открыто видео: {path}'},
    'status.using_camera': {'en': 'Using camera', 'ru': 'Используется камера'},
}


def set_language(language: Optional[str]):
    global _current_language
    if language in LANGUAGES:
        _current_language = language
    return _current_language


def get_language() -> str:
    return _current_language


def tr(key: str, **kwargs) -> str:
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    text = entry.get(_current_language) or entry.get(DEFAULT_LANGUAGE) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
