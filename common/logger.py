import logging
import os
from datetime import datetime
from pathlib import Path
from datetime import timedelta
from time import time

FOLDER = 'logs'
LOGGER_NAME = 'default'


def cleanup_old_logs(dir=None):
    folder = dir or Path(FOLDER)
    if not Path.exists(folder):
        return
    for log in Path.iterdir(folder):
        if time() - log.stat().st_mtime > timedelta(weeks=1).total_seconds():
            os.remove(log)


def setup_logger(level, cleanup_old=True, console=False):
    if cleanup_old:
        cleanup_old_logs()
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    _log_format = "[%(levelname)s] %(filename)s %(funcName)s(%(lineno)d): %(message)s"
    Path.mkdir(Path(FOLDER), exist_ok=True)
    handler = logging.StreamHandler()
    if not console:
        logname = f'logs/log_{datetime.now().strftime("%d,%m,%Y_%H;%M;%S")}.txt'
        handler = logging.FileHandler(logname, mode='w')
        handler.setFormatter(logging.Formatter(_log_format))
    logger.addHandler(handler)
    return logger


logger = setup_logger(logging.DEBUG)
