import argparse
from pathlib import Path
from tkinter import Tk

import eye_tracker.common.settings
from eye_tracker.common.logger import logger, turn_logging_on
from eye_tracker.common.program import save_data, exit_program
from eye_tracker.common.settings import settings, SelectedArea, private_settings
from eye_tracker.model.domain_services import Orchestrator
from eye_tracker.view import view_output
from eye_tracker.view.drawing import Processor
from eye_tracker.view.view_model import ViewModel
from eye_tracker.view.window_form import View

import sys
# https://stackoverflow.com/questions/33225086/how-often-does-python-switch-threads
sys.setswitchinterval(1 / (settings.FPS_PROCESSED * 1.5))


def main(args):
    turn_logging_on(logger)
    eye_tracker.common.settings.ROOT_DIR = Path(__file__).absolute().parent
    if args.root_dir:
        eye_tracker.common.settings.ROOT_DIR = args.root_dir
    root = Tk()
    model_core = None
    view_model = None
    try:
        view_model = ViewModel(root)
        form = View(root, view_model)
        view_output._view = form
        view_model.set_view(form)
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
        SelectedArea.remove()
    logger.debug('settings loaded')
    try:
        model_core = Orchestrator(view_model, area=area, debug_on=args.debug)
        view_model.set_model(model_core)
        logger.debug('mainloop started')
        def correctly_destroy_window():
            root.after_cancel(form._planned_task_id)
            root.destroy()
            for mb in form._visible_messageboxes:
                mb.after_cancel(mb._planned_task_id)
                mb.destroy()
        root.protocol("WM_DELETE_WINDOW", correctly_destroy_window)
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
    exit_program(model_core)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Object Tracking Program')
    parser.add_argument('--root_dir', type=str, help='Root directory of the program')
    parser.add_argument('--debug', help='Simulate laser controller connection for debug purpose', action='store_true')
    args = parser.parse_args()
    main(args)
