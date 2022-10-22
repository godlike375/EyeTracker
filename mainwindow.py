from tkinter import Tk

from dispatcher import Dispatcher
from mainform import MainForm
from utils import Settings, FrameStorage, Extractor, Denoiser


if __name__ == '__main__':
    # TODO: сделать кнопки перевыделения границ и объекта, возможно переворота изображения с камеры на каждые 90 градусов
    root = Tk()
    frame_storage = FrameStorage()
    extractor = Extractor(Settings.CAMERA_ID, root, frame_storage)
    form = MainForm(root, frame_storage).setup()
    dispatcher = Dispatcher(root, frame_storage)
    root.mainloop()
