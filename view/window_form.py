from functools import partial
from tkinter import (
    Label, Tk, Frame, Menu,
    TOP, BOTTOM, X, Toplevel,
    Text, Button, LEFT, W,
    messagebox, END, RIGHT,
    IntVar
)
from tkinter.ttk import Progressbar

from PIL import ImageTk

from common.logger import logger
from common.settings import (
    settings, OBJECT, AREA, FLIP_SIDE_NONE, FLIP_SIDE_VERTICAL,
    FLIP_SIDE_HORIZONTAL, RESOLUTIONS, DOWNSCALED_HEIGHT, get_repo_path
)
from view.view_command_process import CommandExecutor

SECOND_LENGTH = 1000
INDICATORS_WIDTH_ADDITION = 20
REVERSED_MENU_HEIGHT_ADDITION = 150
STRAIGHT_MENU_HEIGHT_ADDITION = 20
ZERO_LINE_AND_COLUMN = 0.0
MARGIN_FIELDS = 3
BUTTON_MARGIN = MARGIN_FIELDS * 10


class View:
    def __init__(self, tk: Tk, view_model):
        self._root = tk
        self._view_model = view_model
        self._image_alive_ref = None
        self._interval_ms = int(1 / settings.FPS_VIEWED * SECOND_LENGTH)

        self._video_frame = Frame(self._root)
        self._video_label = Label(self._video_frame)

        self._indicators_frame = Frame(self._video_frame)
        self._tip = Label(self._indicators_frame, text='Подсказка: ')
        self._progress_bar = Progressbar(self._indicators_frame)
        self._settings = None

        self._commands = CommandExecutor(self)

        self._rotate_var = IntVar()
        self._flip_var = IntVar()

        self.setup_menus()
        self.setup_layout()

    def setup_menus(self):
        main_menu = Menu(self._root)
        self._root.config(menu=main_menu)

        calibration_menu = Menu(tearoff=False)
        calibration_menu.add_command(label='Лазер', command=self._view_model.calibrate_laser, activebackground='black')
        calibration_menu.add_command(label='Шумоподавление',
                                     command=self._view_model.calibrate_noise_threshold, activebackground='black')
        calibration_menu.add_command(label='Координатную систему',
                                     command=self._view_model.calibrate_coordinate_system, activebackground='black')
        main_menu.add_cascade(label='Откалибровать', menu=calibration_menu)

        object_callback = partial(self._view_model.new_selection, OBJECT)
        main_menu.add_command(label='Выделить объект', command=object_callback)

        main_menu.add_command(label='Прервать', command=self._view_model.cancel_active_process)

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
        main_menu.add_cascade(label='Повернуть', menu=rotation_menu)

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
        main_menu.add_cascade(label='Отразить', menu=flip_menu)

        manual_menu = Menu(tearoff=False)
        area_callback = partial(self._view_model.new_selection, AREA)
        manual_menu.add_command(label='Выделить область', command=area_callback)
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
        manual_menu.add_cascade(label='Позиционировать лазер', menu=position_menu)
        main_menu.add_cascade(label='Ручное управление', menu=manual_menu)

        main_menu.add_command(label='Настройки', command=self.open_settings)

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
        window_height = DOWNSCALED_HEIGHT
        window_width = RESOLUTIONS[window_height] + INDICATORS_WIDTH_ADDITION
        window_size = f'{window_height + STRAIGHT_MENU_HEIGHT_ADDITION}x{window_width + INDICATORS_WIDTH_ADDITION}' \
            if not reverse else \
            f'{window_width + REVERSED_MENU_HEIGHT_ADDITION}x{window_height + INDICATORS_WIDTH_ADDITION}'
        self._root.geometry(window_size)

        if reverse:
            self._image_alive_ref = None

        logger.debug(f'window size = {window_size}')

    def _processing_loop(self):
        self._root.after(self._interval_ms, self._processing_loop)

        self._commands.exec_queued_commands()

    def check_show_image(self, image):
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
        if self._settings is not None:
            self.focus_on_settings_window()
            return
        self._settings = Toplevel(self._root)
        self._settings.title('Настройки')
        try:
            self._settings.iconbitmap(str(get_repo_path(bundled=True) / "tracking.ico"))
        except Exception:
            logger.warning('tracking.ico not found')

        reset_settings_button = Button(self._settings, command=self._view_model.reset_settings,
                                       text='Сбросить настройки')
        reset_settings_button.pack(pady=MARGIN_FIELDS)

        params = {}
        for param in dir(settings):
            if param.isupper():
                frame = Frame(self._settings)
                frame.pack(fill=X)
                label = Label(frame, text=f'{param} =')
                label.pack(side=LEFT, pady=MARGIN_FIELDS, padx=MARGIN_FIELDS)

                text_param = str(getattr(settings, param))
                edit = Text(frame, width=len(text_param) + 1, height=1)
                params[param] = edit
                edit.pack(side=LEFT, pady=MARGIN_FIELDS, padx=MARGIN_FIELDS)
                edit.insert(ZERO_LINE_AND_COLUMN, text_param)
        pick_color_button = Button(self._settings, command=self._view_model.pick_color, text='Выбрать цвет отрисовки')
        pick_color_button.pack(pady=MARGIN_FIELDS)

        buttons_frame = Frame(self._settings)
        buttons_frame.pack(pady=MARGIN_FIELDS)
        save_settings = partial(self._view_model.save_settings, params)
        exit_settings = partial(self.exit_settings, params)
        self._settings.protocol("WM_DELETE_WINDOW", exit_settings)
        exit_settings_button = Button(buttons_frame, command=exit_settings, text='Закрыть')
        save_button = Button(buttons_frame, command=save_settings, text='Сохранить')
        save_button.pack(padx=BUTTON_MARGIN, side=RIGHT)
        exit_settings_button.pack(padx=BUTTON_MARGIN, side=LEFT)

    def exit_settings(self, params):
        global_settings = [getattr(settings, name) for name in dir(settings) if name.isupper()]
        current_settings = []
        for name, text_edit in params.items():
            text_param = text_edit.get(0.0, END)[:-1]
            try:
                number_param = float(text_param) if '.' in text_param else int(text_param)
            except ValueError:
                self.destroy_settings_window()
                return
            else:
                current_settings.append(number_param)
        if current_settings == global_settings:
            self.destroy_settings_window()
            return
        else:
            exit_confirm = messagebox.askyesno(title='Предупреждение',
                                               message='Имеются несохранённые параметры. '
                                                       'Хотите закрыть окно без сохранения?')
            self.focus_on_settings_window()
            if exit_confirm:
                self.destroy_settings_window()

    def destroy_settings_window(self):
        self._settings.destroy()
        self._settings = None

    def focus_on_settings_window(self):
        if self._settings:
            self._settings.focus_force()
