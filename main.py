from tkinter import Tk, messagebox
from traceback import print_exc

from management_core import EventDispatcher, FrameStorage, Extractor
from view.window import Window
from model.settings import Settings


if __name__ == '__main__':
    try:
        Settings.load()
    except Exception as e:
        messagebox.showerror(title='Ошибка загрузки конфигурации', message=f'{e}')
    try:
        root = Tk()
        frame_storage = FrameStorage()
        extractor = Extractor(Settings.CAMERA_ID, frame_storage)
        dispatcher = EventDispatcher(root, frame_storage)
        form = Window(root, frame_storage, dispatcher).setup()
        root.after(2000, dispatcher.center_laser)
        root.mainloop()
    except Exception as e:
        messagebox.showerror(title='Фатальная ошибка', message=f'{e}')
        print_exc()
    else:
        Settings.save()
        dispatcher.stop_thread()
        dispatcher.center_laser()
        extractor.stop_thread()
        # TODO: остановить все второстепенные потоки