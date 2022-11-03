import logging
from tkinter import Label, Tk, Frame, Button, TOP, BOTTOM, LEFT, RIGHT

from PIL import ImageTk

from common.utils import LOGGER_NAME
from management_core import ViewModel, FrameStorage
from model.settings import Settings

SECOND_LENGTH = 1000
RESOLUTIONS = {1280: 750, 800: 630, 640: 510}
PADDING_X = 16
PADDING_Y = 4

logger = logging.getLogger(LOGGER_NAME)


class Window:
    def __init__(self, tk: Tk, frame_storage: FrameStorage, dispatcher: ViewModel):
        self.window = tk
        self.image_alive_ref = None
        self.imageFrame = Frame(self.window, width=600, height=800)
        self.buttonFrame = Frame(self.window, background='white')
        self.select_area_rect = Button(self.buttonFrame, text='Выделение зоны',
                                       command=dispatcher.reset_area_selection)
        self.select_object_rect = Button(self.buttonFrame, text='Выделение объекта',
                                         command=dispatcher.reset_object_selection)
        self.calibrate_laser = Button(self.buttonFrame, text='Откалибровать лазер',
                                      command=dispatcher.calibrate_laser)
        self.dispatcher = dispatcher
        self.video = Label(self.imageFrame)
        self.frame_storage = frame_storage
        self.interval_ms = int(FrameStorage.FRAME_INTERVAL * SECOND_LENGTH)
        self.show_image()

    def setup(self):
        self.window.title('Eye tracker')
        WINDOW_HEIGHT = Settings.CAMERA_MAX_RESOLUTION
        WINDOW_WIDTH = RESOLUTIONS[WINDOW_HEIGHT]
        window_size = f'{WINDOW_HEIGHT}x{WINDOW_WIDTH}'
        logger.debug(f'window size = {window_size}')
        self.window.geometry(window_size)
        self.window.configure(background='white')
        self.imageFrame.pack(side=BOTTOM)
        self.calibrate_laser.pack(side=LEFT, padx=PADDING_X, pady=PADDING_Y)
        self.select_area_rect.pack(side=LEFT, padx=PADDING_X, pady=PADDING_Y)
        self.select_object_rect.pack(side=RIGHT, padx=PADDING_X, pady=PADDING_Y)
        self.video.pack(side=BOTTOM)
        self.buttonFrame.pack(side=TOP)
        self.select_object_rect['state'] = 'disabled'
        return self

    def show_image(self):
        # TODO: возможно вьюшка должна дергать вьюмодел, что теоретически должно заставлять
        # TODO: работать модель и возвращать результат в эту функцию для отрисовки
        frame = self.frame_storage.get_image()
        imgtk = ImageTk.PhotoImage(image=frame)
        # !!! если не сохранить ссылку на этот объект, то объект тут же удалится и не будет отображаться картинка
        self.image_alive_ref = imgtk
        self.video.configure(image=imgtk)
        self.window.after(self.interval_ms, self.show_image)
        if self.dispatcher.area_selector.is_selected() and self.select_object_rect['state'] == 'disabled':
            logger.debug('area selected')
            self.select_object_rect['state'] = 'normal'
