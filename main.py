import argparse
import logging
from pathlib import Path
from tkinter import Tk, messagebox

import common.settings
from common.settings import Settings, SelectedArea
from common.thread_helpers import LOGGER_NAME
from model.logical_core import Model
from view.view_model import ViewModel
from view.window_form import View

logger = logging.getLogger(LOGGER_NAME)


def setup_logger(level):
    logger.setLevel(level)
    _log_format = f"[%(levelname)s] %(filename)s %(funcName)s(%(lineno)d): %(message)s"
    handler = logging.FileHandler('log.txt', mode='w')
    handler.setFormatter(logging.Formatter(_log_format))
    logger.addHandler(handler)


def main(args):
    setup_logger(logging.DEBUG)
    common.settings.ROOT_DIR = Path(__file__).absolute().parent
    if args.root_dir:
        common.settings.ROOT_DIR = args.root_dir
    try:
        Settings.load()
        area = SelectedArea.load()
        logger.debug('settings loaded')
    except Exception as e:
        messagebox.showerror(title='Ошибка загрузки конфигурации', message=f'{e}')
    try:
        root = Tk()
        view_model = ViewModel(root)
        form = View(root, view_model).setup()
        view_model.set_view(form)
        model_core = Model(view_model, area=area)
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Object Tracking Program')
    parser.add_argument('--root_dir', type=str, help='Root directory of the program')
    args = parser.parse_args()
    main(args)
