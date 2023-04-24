import os
import sys
from pathlib import Path

from common.logger import logger
from common.settings import settings, private_settings, AREA, SelectedArea


def exit_program(model_core, restart=False):
    # TODO: главный поток завершить, иначе через модель не выйти
    #  или послать команду модели отложенную
    model_core.stop_thread()
    settings.save()
    private_settings.save()
    save_data(model_core)
    try:
        os.execv(str(Path.cwd() / sys.argv[0]), [sys.argv[0]])
    except OSError:
        logger.debug('could not restart the program (exec from .py?)')
        sys.exit()
    logger.debug(f'program {"exited" if not restart else "restarted"} ')
    sys.exit()


def save_data(model_core):
    settings.save()
    private_settings.save()
    area_is_selected = model_core.selecting.selector_is_selected(AREA)
    if area_is_selected:
        if model_core.threshold_calibrator.in_progress or model_core.coordinate_calibrator.in_progress \
                and model_core.previous_area:
            SelectedArea.save(model_core.previous_area.points)
        else:
            area_selector = model_core.selecting.get_selector(AREA)
            SelectedArea.save(area_selector.points)
    else:
        SelectedArea.remove()
    logger.debug('settings saved')
