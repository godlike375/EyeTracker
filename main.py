from tkinter import Tk, messagebox
from traceback import print_exc

from dispatcher import EventDispatcher
from mainform import MainForm
from utils import Settings, FrameStorage, Extractor


if __name__ == '__main__':
    # TODO: сделать кнопки перевыделения границ и объекта, возможно переворота изображения с камеры на каждые 90 градусов
    try:
        root = Tk()
        frame_storage = FrameStorage()
        extractor = Extractor(Settings.CAMERA_ID, root, frame_storage)
        dispatcher = EventDispatcher(root, frame_storage)
        form = MainForm(root, frame_storage, dispatcher).setup()
        root.mainloop()
    except Exception as e:
        messagebox.showerror(title='fatal error', message=f'{e}')
        print_exc()

