from tkinter import Tk

from dispatcher import Dispatcher
from mainform import MainForm
from utils import Settings, FrameStorage, Extractor

if __name__ == '__main__':
    root = Tk()
    frame_storage = FrameStorage()
    extractor = Extractor(Settings.CAMERA_ID, root, frame_storage)
    form = MainForm(root, frame_storage).setup()
    dispatcher = Dispatcher(root, frame_storage)
    root.mainloop()
