from tkinter import (
    Label, Tk, Frame, Menu,
    TOP, BOTTOM, X, Toplevel,
    Text, Button, LEFT, W,
    messagebox, END, RIGHT,
                     )
from tkinter.ttk import Progressbar
from functools import partial

from PIL import ImageTk

from common.settings import (
    settings, AREA, OBJECT,FLIP_SIDE_NONE, FLIP_SIDE_VERTICAL,
    FLIP_SIDE_HORIZONTAL, RESOLUTIONS, DOWNSCALED_HEIGHT, get_repo_path
                             )
from common.logger import logger

SECOND_LENGTH = 1000
INDICATORS_WIDTH_ADDITION = 20
REVERSED_MENU_HEIGHT_ADDITION = 135
ZERO_LINE_AND_COLUMN = 0.0
MARGIN_FIELDS = 3
BUTTON_MARGIN = MARGIN_FIELDS * 10


class View:
    def __init__(self, tk: Tk, view_model):
        self._root = tk
        self._view_model = view_model
        self._last_image_height = 0
        self._last_image_width = 0
        self._current_image = None
        self._prev_image = None
        self._image_alive_ref = None
        self._interval_ms = int(1 / settings.FPS_VIEWED * SECOND_LENGTH)

        self._video_frame = Frame(self._root)
        self._video_label = Label(self._video_frame)

        self._indicators_frame = Frame(self._video_frame)
        self._tip = Label(self._indicators_frame, text='Подсказка: ')
        self._progress_bar = Progressbar(self._indicators_frame)
        self._settings = None

        self.setup_menus()
        self.setup_layout()

    def setup_menus(self):
        main_menu = Menu(self._root)
        self._root.config(menu=main_menu)

        area_callback = partial(self._view_model.new_selection, AREA)
        object_callback = partial(self._view_model.new_selection, OBJECT)
        selection_menu = Menu(tearoff=False)
        selection_menu.add_command(label='Область', command=area_callback)
        selection_menu.add_command(label='Объект', command=object_callback)
        main_menu.add_cascade(label='Выделить', menu=selection_menu)

        main_menu.add_command(label='Прервать', command=self._view_model.cancel_active_process)

        calibration_menu = Menu(tearoff=False)
        calibration_menu.add_command(label='Лазер', command=self._view_model.calibrate_laser)
        calibration_menu.add_command(label='Шумоподавление',
                                     command=self._view_model.calibrate_noise_threshold)
        main_menu.add_cascade(label='Откалибровать', menu=calibration_menu)

        position_menu = Menu(tearoff=False)
        MAX_LASER_RANGE_PLUS_MINUS = settings.MAX_LASER_RANGE_PLUS_MINUS
        move_left_top = partial(self._view_model.move_laser, -MAX_LASER_RANGE_PLUS_MINUS, -MAX_LASER_RANGE_PLUS_MINUS)
        move_right_top = partial(self._view_model.move_laser, MAX_LASER_RANGE_PLUS_MINUS, -MAX_LASER_RANGE_PLUS_MINUS)
        move_left_bottom = partial(self._view_model.move_laser, -MAX_LASER_RANGE_PLUS_MINUS, MAX_LASER_RANGE_PLUS_MINUS)
        move_right_bottom = partial(self._view_model.move_laser, MAX_LASER_RANGE_PLUS_MINUS, MAX_LASER_RANGE_PLUS_MINUS)
        move_center = partial(self._view_model.move_laser, 0, 0)
        position_menu.add_command(label='Лево верх', command=move_left_top)
        position_menu.add_command(label='Право верх', command=move_right_top)
        position_menu.add_command(label='Лево низ', command=move_left_bottom)
        position_menu.add_command(label='Право низ', command=move_right_bottom)
        position_menu.add_command(label='Центр', command=move_center)
        main_menu.add_cascade(label='Позиционировать лазер', menu=position_menu)

        rotation_menu = Menu(tearoff=False)
        rotate_0 = partial(self._view_model.rotate_image, 0)
        rotate_90 = partial(self._view_model.rotate_image, 90)
        rotate_180 = partial(self._view_model.rotate_image, 180)
        rotate_270 = partial(self._view_model.rotate_image, 270)
        rotation_menu.add_command(label='0°', command=rotate_0)
        rotation_menu.add_command(label='90°', command=rotate_90)
        rotation_menu.add_command(label='180°', command=rotate_180)
        rotation_menu.add_command(label='270°', command=rotate_270)
        main_menu.add_cascade(label='Повернуть', menu=rotation_menu)

        flip_menu = Menu(tearoff=False)
        flip_none = partial(self._view_model.flip_image, side=FLIP_SIDE_NONE)
        flip_vertical = partial(self._view_model.flip_image, side=FLIP_SIDE_VERTICAL)
        flip_horizontal = partial(self._view_model.flip_image, side=FLIP_SIDE_HORIZONTAL)
        flip_menu.add_command(label='Не отражать', command=flip_none)
        flip_menu.add_command(label='По вертикали', command=flip_vertical)
        flip_menu.add_command(label='По горизонтали', command=flip_horizontal)
        main_menu.add_cascade(label='Отразить', menu=flip_menu)

        main_menu.add_command(label='Настройки', command=self.open_settings)

    def setup_layout(self):
        self._root.title('Eye tracker')
        try:
            self._root.iconbitmap(str(get_repo_path(bundled=True) / "tracking.ico"))
        except:
            logger.debug('tracking.ico not found')

        self.setup_window_geometry()

        self._root.configure(background='white')

        self._video_frame.pack(side=TOP)
        self._video_label.pack(side=TOP)
        self._indicators_frame.pack(side=BOTTOM, fill=X)
        self._tip.pack(side=TOP, anchor=W)
        self.progress_bar_set_visibility(False)
        self.show_image()

    def setup_window_geometry(self, reverse=False):
        window_height = DOWNSCALED_HEIGHT
        window_width = RESOLUTIONS[window_height] + INDICATORS_WIDTH_ADDITION

        self.window_height = window_height if not reverse else window_width
        self.window_width = window_width if not reverse else window_height
        window_size = f'{window_height}x{window_width + INDICATORS_WIDTH_ADDITION}' if not reverse else \
            f'{window_width + REVERSED_MENU_HEIGHT_ADDITION}x{window_height + INDICATORS_WIDTH_ADDITION}'
        self._root.geometry(window_size)

        if reverse:
            self._image_alive_ref = None

        logger.debug(f'window size = {window_size}')

    def set_current_image(self, img):
        self._prev_image = self._current_image
        self._current_image = img

    def show_image(self):
        self._root.after(self._interval_ms, self.show_image)
        if self._current_image is None or self._prev_image is self._current_image:
            return
        image = self._current_image

        if image.width != self._last_image_width or image.height != self._last_image_height:
            self._image_alive_ref = None
            self._last_image_height = image.height
            self._last_image_width = image.width

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

    def progress_bar_set_value(self, val):
        self._progress_bar.config(value=val)

    def progress_bar_get_value(self):
        return self._progress_bar['value']

    def set_tip(self, text):
        self._tip.config(text=text)

    def open_settings(self):
        if self._settings is not None:
            self.focus_on_settings_window()
            return
        self._settings = Toplevel(self._root)
        self._settings.title('Настройки')

        reset_settings_button = Button(self._settings, command=self._view_model.reset_settings, text='Сбросить настройки')
        reset_settings_button.pack(pady=MARGIN_FIELDS)

        params = {}
        for param in dir(settings):
            if param.isupper():
                frame = Frame(self._settings)
                frame.pack(fill=X)
                label = Label(frame, text=f'{param} =')
                label.pack(side=LEFT, pady=MARGIN_FIELDS, padx=MARGIN_FIELDS)

                text_param = str(getattr(settings, param))
                edit = Text(frame, width=len(text_param)+1, height=1)
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