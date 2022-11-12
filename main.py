from tkinter import Tk, messagebox
import logging


from model.logical_core import Model
from view.view_model import ViewModel
from common.settings import Settings, SelectedArea
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
        left_top, right_bottom = SelectedArea.load()
        logger.debug('settings loaded')
    except Exception as e:
        messagebox.showerror(title='Ошибка загрузки конфигурации', message=f'{e}')
    try:
        root = Tk()
        view_model = ViewModel(root)
        form = View(root, view_model).setup()
        view_model.set_view(form)
        model_core = Model(view_model, area=(left_top, right_bottom),)
        view_model.set_model(model_core)
        logger.debug('mainloop started')
        root.mainloop()
        logger.debug('mainloop finished')
    except Exception as e:
        ViewModel.show_message(title='Фатальная ошибка', message=f'{e}')
        logger.exception(e)
    else:
        model_core.center_laser()
        model_core.stop_thread()
        Settings.save()
        area_selector = model_core.get_or_create_selector('area')
        if area_selector.is_selected():
            SelectedArea.save(area_selector.left_top, area_selector.right_bottom)
        logger.debug('settings saved')
