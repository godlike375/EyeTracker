from functools import partial
from tkinter import (
    Label, Tk, Frame, Menu,
    TOP, BOTTOM, X, W, IntVar
)
from tkinter.ttk import Progressbar

from PIL import ImageTk

from model.common.logger import logger
from model.common.settings import (
    settings, OBJECT, AREA, FLIP_SIDE_NONE, FLIP_SIDE_VERTICAL,
    FLIP_SIDE_HORIZONTAL, RESOLUTIONS, DOWNSCALED_WIDTH, get_repo_path
)
from model.command_processor import CommandExecutor
from view.view_model import (
    CALIBRATION_MENU_NAME,
    SELECTION_MENU_NAME,
    ROTATION_MENU_NAME,
    FLIP_MENU_NAME,
    MANUAL_MENU_NAME
)
from view.window_settings import WindowSettings

SECOND_LENGTH = 1000
INDICATORS_HEIGHT_ADDITION = 45
REQUIRED_MENU_WIDTH = 780


class View:
    def __init__(self, tk: Tk, view_model):
        self._root = tk
        self._view_model = view_model
        self._image_alive_ref = None
        self._current_image = None
        self._previous_image = None
        self._interval_ms = int(1 / settings.FPS_VIEWED * SECOND_LENGTH)

        self._video_frame = Frame(self._root)
        self._video_label = Label(self._video_frame)

        self._indicators_frame = Frame(self._video_frame)
        self._tip = Label(self._indicators_frame, text='Подсказка: ')
        self._progress_bar = Progressbar(self._indicators_frame)
        self._settings = WindowSettings(self._root, self._view_model)

        self._commands = CommandExecutor()

        self._rotate_var = IntVar()
        self._flip_var = IntVar()
        self._menu = None

        self.setup_menus()
        self.setup_layout()

    def setup_menus(self):
        main_menu = Menu(self._root)
        self._menu = main_menu
        self._root.config(menu=main_menu)

        calibration_menu = self.setup_calibration_menu()
        main_menu.add_cascade(label=CALIBRATION_MENU_NAME, menu=calibration_menu)

        object_callback = partial(self._view_model.new_selection, OBJECT)
        main_menu.add_command(label=SELECTION_MENU_NAME, command=object_callback)

        main_menu.add_command(label='Прервать', command=self._view_model.cancel_active_process)

        rotation_menu = self.setup_rotation_menu()
        main_menu.add_cascade(label=ROTATION_MENU_NAME, menu=rotation_menu)

        flip_menu = self.setup_flip_menu()
        main_menu.add_cascade(label=FLIP_MENU_NAME, menu=flip_menu)

        manual_menu = Menu(tearoff=False)
        area_callback = partial(self._view_model.new_selection, AREA)
        manual_menu.add_command(label='Выделить область', command=area_callback)

        position_menu = self.setup_position_menu()
        manual_menu.add_cascade(label='Позиционировать лазер', menu=position_menu)
        main_menu.add_cascade(label=MANUAL_MENU_NAME, menu=manual_menu)

        main_menu.add_command(label='Настройки', command=self.open_settings)

    def setup_calibration_menu(self):
        calibration_menu = Menu(tearoff=False)
        calibration_menu.add_command(label='Лазер', command=self._view_model.calibrate_laser, activebackground='black')
        calibration_menu.add_command(label='Шумоподавление',
                                     command=self._view_model.calibrate_noise_threshold, activebackground='black')
        calibration_menu.add_command(label='Координатную систему',
                                     command=self._view_model.calibrate_coordinate_system, activebackground='black')
        return calibration_menu

    def setup_rotation_menu(self):
        rotation_menu = Menu(tearoff=False)
        rotate_0 = partial(self._view_model.rotate_image, 0)
        rotate_90 = partial(self._view_model.rotate_image, 90)
        rotate_180 = partial(self._view_model.rotate_image, 180)
        rotate_270 = partial(self._view_model.rotate_image, 270)
        self._rotate_var = IntVar()
        rotation_menu.add_radiobutton(label='0°', command=rotate_0,
                                      value=0, variable=self._rotate_var, activebackground='black')
        rotation_menu.add_radiobutton(label='90°', command=rotate_90,
                                      value=90, variable=self._rotate_var, activebackground='black')
        rotation_menu.add_radiobutton(label='180°', command=rotate_180,
                                      value=180, variable=self._rotate_var, activebackground='black')
        rotation_menu.add_radiobutton(label='270°', command=rotate_270,
                                      value=270, variable=self._rotate_var, activebackground='black')
        return rotation_menu

    def setup_flip_menu(self):
        flip_menu = Menu(tearoff=False)
        flip_none = partial(self._view_model.flip_image, side=FLIP_SIDE_NONE)
        flip_vertical = partial(self._view_model.flip_image, side=FLIP_SIDE_VERTICAL)
        flip_horizontal = partial(self._view_model.flip_image, side=FLIP_SIDE_HORIZONTAL)
        flip_menu.add_radiobutton(label='Не отражать', command=flip_none,
                                  value=FLIP_SIDE_NONE, variable=self._flip_var, activebackground='black')
        flip_menu.add_radiobutton(label='По вертикали', command=flip_vertical,
                                  value=FLIP_SIDE_VERTICAL, variable=self._flip_var, activebackground='black')
        flip_menu.add_radiobutton(label='По горизонтали', command=flip_horizontal,
                                  value=FLIP_SIDE_HORIZONTAL, variable=self._flip_var, activebackground='black')
        return flip_menu

    def setup_position_menu(self):
        position_menu = Menu(tearoff=False)

        MAX_LASER_RANGE = settings.MAX_LASER_RANGE_PLUS_MINUS
        move_left_top = partial(self._view_model.move_laser, -MAX_LASER_RANGE, -MAX_LASER_RANGE)
        move_right_top = partial(self._view_model.move_laser, MAX_LASER_RANGE, -MAX_LASER_RANGE)
        move_left_bottom = partial(self._view_model.move_laser, -MAX_LASER_RANGE, MAX_LASER_RANGE)
        move_right_bottom = partial(self._view_model.move_laser, MAX_LASER_RANGE, MAX_LASER_RANGE)
        move_center = partial(self._view_model.move_laser, 0, 0)
        position_menu.add_radiobutton(label='Лево верх', command=move_left_top, activebackground='black')
        position_menu.add_radiobutton(label='Право верх', command=move_right_top, activebackground='black')
        position_menu.add_radiobutton(label='Лево низ', command=move_left_bottom, activebackground='black')
        position_menu.add_radiobutton(label='Право низ', command=move_right_bottom, activebackground='black')
        position_menu.add_radiobutton(label='Центр', command=move_center, activebackground='black')
        return position_menu

    def setup_layout(self):
        self._root.title('Eye tracker')
        try:
            self._root.iconbitmap(str(get_repo_path(bundled=True) / "tracking.ico"))
        except Exception:
            logger.warning('tracking.ico not found')

        self.setup_window_geometry()

        self._root.configure(background='white')

        self._video_frame.pack(side=TOP)
        self._video_label.pack(side=TOP)
        self._indicators_frame.pack(side=BOTTOM, fill=X)
        self._tip.pack(side=TOP, anchor=W)
        self.progress_bar_set_visibility(False)
        self._processing_loop()

    def setup_window_geometry(self, reverse=False):
        # ширина окна должна доходить до определенного значения, т.к. формат изображения с камеры зависит от камеры

        window_width = DOWNSCALED_WIDTH
        window_heigth = RESOLUTIONS[window_width]
        window_size = f'{max(REQUIRED_MENU_WIDTH, window_width)}x{window_heigth + INDICATORS_HEIGHT_ADDITION}' \
            if not reverse else \
            f'{max(REQUIRED_MENU_WIDTH, window_heigth)}x{window_width + INDICATORS_HEIGHT_ADDITION}'
        self._root.geometry(window_size)
        self._geometry_changed = True
        self._image_alive_ref = None

        logger.debug(f'window size = {window_size}')

    def _processing_loop(self):
        self._root.after(self._interval_ms, self._processing_loop)
        self.check_show_image(self._current_image)
        self._commands.exec_queued_commands()

    def check_show_image(self, image):
        # WARNING: Выносить процесс отрисовки в исполнение команд от модели - плохая идея
        #  Так сбиваются тайминги отрисовки и сбросов кадра (image_alive_ref = None становится не None и картинка
        #  не полностью переворачивается. Очень трудновоспроизводимый баг, рандомный
        if image is None or image == self._previous_image:
            return

        self._previous_image = image

        if self._image_alive_ref is not None:
            # Для повышения производительности вставляем в готовый лейбл изображение, не пересоздавая
            self._image_alive_ref.paste(image)
        else:
            self._image_alive_ref = ImageTk.PhotoImage(image=image)
            self._video_label.configure(image=self._image_alive_ref)

    def progress_bar_set_visibility(self, visible):
        if not visible:
            self._progress_bar.pack_forget()
        else:
            self._progress_bar.pack(fill=X)

    def set_progress(self, val):
        self._progress_bar.config(value=val)

    def get_progress(self):
        return self._progress_bar['value']

    def set_tip(self, tip):
        self._tip.config(text=tip)

    def queue_command(self, command):
        self._commands.queue_command(command)

    def open_settings(self):
        self._settings.open_settings()

    def exit_settings(self, params):
        self._settings.exit_settings(params)

    def destroy_settings_window(self):
        self._settings.destroy_settings_window()

    def focus_on_settings_window(self):
        self._settings.focus_on_settings_window()

