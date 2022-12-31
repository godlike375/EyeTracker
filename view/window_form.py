from tkinter import (
    Label, Tk, Frame, Button, TOP,
    BOTTOM, LEFT, RIGHT
)
from functools import partial

from PIL import ImageTk

from common.settings import Settings, AREA, OBJECT
from common.logger import logger

SECOND_LENGTH = 1000
RESOLUTIONS = {1280: 750, 800: 630, 640: 510}
PADDING_X = 16
PADDING_Y = 4


class View:
    def __init__(self, tk: Tk, view_model):
        self._root = tk
        self._image_alive_ref = None
        self._image_frame = Frame(self._root, width=600, height=800)
        self._button_frame = Frame(self._root, background='white')
        area_callback = partial(view_model.new_selection, AREA)
        object_callback = partial(view_model.new_selection, OBJECT)
        self._select_area_rect = Button(self._button_frame, text='Выделение зоны',
                                        command=area_callback)
        self._select_object_rect = Button(self._button_frame, text='Выделение объекта',
                                          command=object_callback)
        self._calibrate_laser = Button(self._button_frame, text='Откалибровать лазер',
                                       command=view_model.calibrate_laser)
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
        self._calibrate_laser.pack(side=LEFT, padx=PADDING_X, pady=PADDING_Y)
        self._select_area_rect.pack(side=LEFT, padx=PADDING_X, pady=PADDING_Y)
        self._select_object_rect.pack(side=RIGHT, padx=PADDING_X, pady=PADDING_Y)
        self._video_label.pack(side=BOTTOM)
        self._button_frame.pack(side=TOP)
        self._select_object_rect['state'] = 'disabled'
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
        if self.view_model.selector_is_selected(AREA) and self._select_object_rect['state'] == 'disabled':
            logger.debug('area selected')
            self._select_object_rect['state'] = 'normal'
