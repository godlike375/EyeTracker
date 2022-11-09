from tkinter import Tk, messagebox
import logging

from model.logical_core import Model
from view.view_model import ViewModel
from common.settings import Settings
from view.window_form import View
from common.thread_helpers import LOGGER_NAME

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
        view_model = ViewModel(root)
        form = View(root, view_model).setup()
        view_model.set_view(form)
        frame_controller = Model(view_model)
        view_model.set_model(frame_controller)
        logger.debug('mainloop started')
        root.mainloop()
        logger.debug('mainloop finished')
    except Exception as e:
        messagebox.showerror(title='Фатальная ошибка', message=f'{e}')
        logger.exception(e)
    else:
        frame_controller.center_laser()
        frame_controller.stop_thread()
    finally:
        Settings.save()
        logger.debug('settings saved')
        # TODO: добавить сохранение зоны в файл, чтобы каждый раз не перевыделять

    # TODO: вынести left_top, right_bottom в класс Rect
    # TODO: messagebox вынести в отдельный интерфейс пользовательских ошибок, ибо это должна быть абстракция
