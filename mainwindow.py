from tkinter import Tk

from utils import Settings
from mainform import MainForm
from frame_process import Extractor, FrameStorage
from dispatcher import Dispatcher

if __name__ == '__main__':
    root = Tk()
    frame_storage = FrameStorage()
    extractor = Extractor(Settings.CAMERA_ID, root, frame_storage)
    form = MainForm(root, frame_storage).setup()
    dispatcher = Dispatcher(root, frame_storage)
    root.mainloop()