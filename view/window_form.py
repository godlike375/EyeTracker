from tkinter import Label, Tk, Frame, Menu, TOP, BOTTOM, Button
from functools import partial

from PIL import ImageTk

from common.settings import Settings, AREA, OBJECT
from common.logger import logger

SECOND_LENGTH = 1000
RESOLUTIONS = {1280: 720, 800: 600, 640: 480}


class View:
    def __init__(self, tk: Tk, view_model):
        self._root = tk
        self._image_alive_ref = None
        self._image_frame = Frame(self._root)
        self._button_frame = Frame(self._root, background='white')
        area_callback = partial(view_model.new_selection, AREA)
        object_callback = partial(view_model.new_selection, OBJECT)
        main_menu = Menu(tk)
        tk.config(menu=main_menu)
        main_menu.add_command(label='Выделение зоны', command=area_callback)
        main_menu.add_command(label='Выделение объекта', command=object_callback)
        main_menu.add_command(label='Откалибровать лазер', command=view_model.calibrate_laser)

        move_left_top = partial(view_model.move_laser, -Settings.MAX_RANGE, -Settings.MAX_RANGE)
        move_right_top = partial(view_model.move_laser, Settings.MAX_RANGE, -Settings.MAX_RANGE)
        move_left_bottom = partial(view_model.move_laser, -Settings.MAX_RANGE, Settings.MAX_RANGE)
        move_right_bottom = partial(view_model.move_laser, Settings.MAX_RANGE, Settings.MAX_RANGE)
        self._left_top = Button(self._button_frame, text='Лево верх',
                                command=move_left_top)
        self._right_top = Button(self._button_frame, text='Право верх',
                                 command=move_right_top)
        self._left_bottom = Button(self._button_frame, text='Лево низ',
                                   command=move_left_bottom)
        self._right_bottom = Button(self._button_frame, text='Право низ',
                                    command=move_right_bottom)
        calibration_menu = Menu()
        calibration_menu.add_command(label='Лево верх', command=move_left_top)
        calibration_menu.add_command(label='Право верх', command=move_right_top)
        calibration_menu.add_command(label='Лево низ', command=move_left_bottom)
        calibration_menu.add_command(label='Право низ', command=move_right_bottom)
        main_menu.add_cascade(label='позиционирование лазера', menu=calibration_menu)

        self.view_model = view_model
        self._video_label = Label(self._image_frame)
        self.interval_ms = int(1 / Settings.FPS_VIEWED * SECOND_LENGTH)
        self._current_image = None

    def setup(self):
        self._root.title('Eye tracker')
        WINDOW_HEIGHT = Settings.CAMERA_MAX_RESOLUTION
        WINDOW_WIDTH = RESOLUTIONS[WINDOW_HEIGHT]
        window_size = f'{WINDOW_HEIGHT}x{WINDOW_WIDTH}'
        logger.debug(f'window size = {window_size}')
        self._root.geometry(window_size)
        self._root.configure(background='white')
        self._image_frame.pack(side=BOTTOM)
        self._video_label.pack(side=BOTTOM)
        self._button_frame.pack(side=TOP)
        self.show_image()
        return self

    def set_current_image(self, img):
        if img is None:
            raise RuntimeError('processed image is None')
        self._current_image = img

    def show_image(self):
        self._root.after(self.interval_ms, self.show_image)
        if self._current_image is None:
            return
        image = self._current_image
        if self._image_alive_ref is not None:
            self._image_alive_ref.paste(image)
        else:
            imgtk = ImageTk.PhotoImage(image=image)
            # сохранять ссылку на объект обязательно, иначе он будет собираться GC и не показываться
            self._image_alive_ref = imgtk
            self._video_label.configure(image=imgtk)
        # TODO: запретить нажимать позиционирование во время трекинга и
        #  выделение объекта без выделенной зоны
        #if self.view_model.selector_is_selected(AREA)
