import argparse
from pathlib import Path
from tkinter import Tk

import common.settings
from common.logger import logger
from common.settings import settings, SelectedArea
from model.domain_services import Orchestrator
from view.view_model import ViewModel
from view.window_form import View
from view import view_output


def main(args):
    common.settings.ROOT_DIR = Path(__file__).absolute().parent
    if args.root_dir:
        common.settings.ROOT_DIR = args.root_dir
    root = Tk()
    try:
        settings.load()
    except Exception as e:
        view_output.show_message(title='Ошибка загрузки конфигурации',
                            message=f'{e} \nРабота программы будет продолжена, но возможны сбои в работе.'
                                    f' Рекоммендуется перезагрузка')
        logger.exception(e)
    area = None
    try:
        area = SelectedArea.load()
    except Exception as e:
        view_output.show_warning(message=f'Ошибка загрузки ранее выделенной области \n{e} \nРабота программы будет продолжена')
        logger.exception(e)
    logger.debug('settings loaded')
    try:
        view_model = ViewModel(root)
        form = View(root, view_model)
        view_model.set_view(form)
        model_core = Orchestrator(view_model, area=area)
        view_model.set_model(model_core)
        logger.debug('mainloop started')
        root.mainloop()
        logger.debug('mainloop finished')
    except Exception as e:
        view_output.show_message(title='Фатальная ошибка', message=f'{e}')
        logger.exception(e)
    else:
        model_core.laser_service.center_laser()
        model_core.stop_thread()
        settings.save()
        area_selector = model_core.get_or_create_selector('area')
        if area_selector.is_selected:
            SelectedArea.save(area_selector.points)
        logger.debug('settings saved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Object Tracking Program')
    parser.add_argument('--root_dir', type=str, help='Root directory of the program')
    args = parser.parse_args()
    main(args)
