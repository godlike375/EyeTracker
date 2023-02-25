from tkinter import (
    Label, Tk, Frame, Menu,
    TOP, BOTTOM, X, Toplevel,
    Text, Button
                     )
from tkinter.ttk import Progressbar
from functools import partial

from PIL import ImageTk

from common.settings import Settings, AREA, OBJECT
from common.logger import logger

SECOND_LENGTH = 1000
RESOLUTIONS = {1280: 720, 800: 600, 640: 480}
WIDTH_OFFSET = 40


class View:
    def __init__(self, tk: Tk, view_model):
        # TODO: отрефакторить код
        self._root = tk
        self._view_model = view_model
        self.interval_ms = int(1 / Settings.FPS_VIEWED * SECOND_LENGTH)
        self._current_image = None
        self._image_alive_ref = None

        self._video_frame = Frame(self._root)
        self._video_label = Label(self._video_frame)

        self._under_menu_frame = Frame(self._video_frame)
        self._progress_bar = Progressbar(self._under_menu_frame)

        self.setup_menus()
        self.setup_layout()

    def setup_menus(self):
        main_menu = Menu(self._root)
        self._root.config(menu=main_menu)
        area_callback = partial(self._view_model.new_selection, AREA)
        object_callback = partial(self._view_model.new_selection, OBJECT)
        main_menu.add_command(label='Выделение зоны', command=area_callback)
        main_menu.add_command(label='Выделение объекта', command=object_callback)
        main_menu.add_command(label='Откалибровать лазер', command=self._view_model.calibrate_laser)
        main_menu.add_command(label='Откалибровать шумоподавление', command=self._view_model.calibrate_noise_threshold)
        main_menu.add_command(label='Остановить трекинг', command=self._view_model.stop_tracking)
        # TODO: MUST HAVE сделать сценарии использования (мастер настройки), чтобы пользователю не нужно было думать
        #  о последовательности действий для настройки

        move_left_top = partial(self._view_model.move_laser, -Settings.MAX_RANGE, -Settings.MAX_RANGE)
        move_right_top = partial(self._view_model.move_laser, Settings.MAX_RANGE, -Settings.MAX_RANGE)
        move_left_bottom = partial(self._view_model.move_laser, -Settings.MAX_RANGE, Settings.MAX_RANGE)
        move_right_bottom = partial(self._view_model.move_laser, Settings.MAX_RANGE, Settings.MAX_RANGE)
        move_center = partial(self._view_model.move_laser, 0, 0)

        position_menu = Menu()
        position_menu.add_command(label='Лево верх', command=move_left_top)
        position_menu.add_command(label='Право верх', command=move_right_top)
        position_menu.add_command(label='Лево низ', command=move_left_bottom)
        position_menu.add_command(label='Право низ', command=move_right_bottom)
        position_menu.add_command(label='Центр', command=move_center)
        main_menu.add_cascade(label='Позиционирование лазера', menu=position_menu)
        main_menu.add_command(label='Настройки', command=self.open_settings)

    def setup_layout(self):
        self._root.title('Eye tracker')

        WINDOW_HEIGHT = Settings.CAMERA_MAX_RESOLUTION
        self.window_height = WINDOW_HEIGHT
        WINDOW_WIDTH = RESOLUTIONS[WINDOW_HEIGHT] + WIDTH_OFFSET
        self.window_width = WINDOW_WIDTH
        window_size = f'{WINDOW_HEIGHT}x{WINDOW_WIDTH}'
        logger.debug(f'window size = {window_size}')
        self._root.geometry(window_size)
        self._root.configure(background='white')

        self._video_frame.pack(side=BOTTOM)
        self._video_label.pack(side=BOTTOM)
        self._under_menu_frame.pack(side=TOP, fill=X)
        self.progress_bar_set_visibility(False)
        self.show_image()

    def set_current_image(self, img):
        self._current_image = img

    def show_image(self):
        self._root.after(self.interval_ms, self.show_image)
        if self._current_image is None:
            return
        image = self._current_image
        if self._image_alive_ref is not None:
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

    def open_settings(self):
        self.settings = Toplevel(self._root)
        self.settings.title('Настройки')
        self._params = {}
        for param in dir(Settings):
            if param.isupper():
                label = Label(self.settings, text=param)
                label.pack()

                edit = Text(self.settings, width=12, height=1)
                self._params[param] = edit
                edit.pack()
                text_param = str(getattr(Settings, param))
                edit.insert(0.0, text_param)
        save_settings = partial(self._view_model.save_settings, self._params)
        save_button = Button(self.settings, command=save_settings, text='Сохранить')
        save_button.pack()
