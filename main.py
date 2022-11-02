from tkinter import Tk, messagebox
import logging

from management_core import EventDispatcher, FrameStorage, Extractor
from model.settings import Settings
from view.window import Window
from common.utils import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)

if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    _log_format = f"[%(levelname)s] %(filename)s %(funcName)s(%(lineno)d): %(message)s"
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_log_format))
    logger.addHandler(handler)
    try:
        Settings.load()
        logger.debug('settings loaded')
    except Exception as e:
        messagebox.showerror(title='Ошибка загрузки конфигурации', message=f'{e}')
    try:
        root = Tk()
        frame_storage = FrameStorage()
        extractor = Extractor(Settings.CAMERA_ID, frame_storage)
        dispatcher = EventDispatcher(root, frame_storage)
        form = Window(root, frame_storage, dispatcher).setup()
        logger.debug('mainloop started')
        root.mainloop()
        logger.debug('mainloop finished')
    except Exception as e:
        messagebox.showerror(title='Фатальная ошибка', message=f'{e}')
        logger.exception(e)
    else:
        dispatcher.center_laser()
        dispatcher.stop_thread()
        extractor.stop_thread()
    finally:
        Settings.save()
        # TODO: добавить сохранение зоны в файл, чтобы каждый раз не перевыделять

    # TODO: вынести left_top, right_bottom в класс Rect
    # TODO: messagebox вынести в отдельный интерфейс пользовательских ошибок, ибо это должна быть абстракция
