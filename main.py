import argparse
from pathlib import Path
from tkinter import Tk

import common.settings
from common.logger import logger
from common.program import save_data
from common.settings import settings, SelectedArea, private_settings
from model.domain_services import Orchestrator
from view import view_output
from view.drawing import Processor
from view.view_model import ViewModel
from view.window_form import View


def main(args):
    common.settings.ROOT_DIR = Path(__file__).absolute().parent
    if args.root_dir:
        common.settings.ROOT_DIR = args.root_dir
    root = Tk()
    try:
        settings.load()
        private_settings.load()
        Processor.load_color()
    except Exception as e:
        view_output.show_error(title='Ошибка загрузки конфигурации',
                               message=f'{e} \nРабота программы будет продолжена, но возможны сбои в работе.'
                                       f' Рекоммендуется перезагрузка')
        logger.exception(e)
    area = None
    try:
        area = SelectedArea.load()
    except Exception as e:
        view_output.show_error(
            message=f'Ошибка загрузки ранее выделенной области \n{e} \nРабота программы будет продолжена')
        logger.exception(e)
    logger.debug('settings loaded')
    try:
        view_model = ViewModel(root)
        form = View(root, view_model)
        view_output._view = form
        view_model.set_view(form)
        model_core = Orchestrator(view_model, area=area, debug_on=args.debug)
        view_model.set_model(model_core)
        logger.debug('mainloop started')
        root.mainloop()
    except Exception as e:
        view_output.show_fatal(f'Произошла фатальная ошибка.\n'
                               f'{e}\n'
                               f'Работа программы не может быть продолжена. '
                               f'Будет произведена попытка сохранения данных')
        logger.exception(e)
        save_data(model_core)
        return
    except KeyboardInterrupt:
        logger.debug('interrupted using KeyboardInterrupt')
    logger.debug('mainloop finished')
    model_core.stop_thread()
    model_core.laser.center_laser()
    save_data(model_core)
    logger.debug('settings saved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Object Tracking Program')
    parser.add_argument('--root_dir', type=str, help='Root directory of the program')
    parser.add_argument('--debug', help='Simulate laser controller connection for debug purpose', action='store_true')
    args = parser.parse_args()
    main(args)
