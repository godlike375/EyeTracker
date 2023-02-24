import pickle
from configparser import ConfigParser
from pathlib import Path

from common.logger import logger


AREA = 'area'
OBJECT = 'object'
FOLDER = 'config'
FILE = 'eyetracker_settings.ini'
AREA_FILE = 'selected_area.pickle'
ROOT_FOLDER = 'EyeTracker'
ROOT_DIR = None


class Settings:
    CAMERA_ID = 0  # the second web-camera
    CAMERA_MAX_RESOLUTION = 640  # max height
    FPS_PROCESSED = 60  # target frames per second
    SERIAL_BAUND_RATE = 115200
    SERIAL_TIMEOUT = 0.01
    SERIAL_PORT = 8
    MEAN_TRACKING_COUNT = 2
    NOISE_THRESHOLD = 0.0
    OBJECT_NOT_MOVING_TIME_SEC = 10
    MAX_RANGE = 6000
    STABLE_POSITION_DURATION = 0.67
    FPS_VIEWED = 30

    @staticmethod
    def get_repo_path(current: Path = None):
        current_path = current or Path.cwd()
        while current_path.name != ROOT_FOLDER:
            if current_path == current_path.parent:
                if ROOT_DIR is not None:
                    return Path(ROOT_DIR)
                logger.exception(f'Корневая директория программы "{ROOT_FOLDER}" не найдена')
                return Path.cwd()
            current_path = current_path.parent
        return current_path

    @staticmethod
    def load(folder: str = FOLDER, file: str = FILE):
        base_path = Settings.get_repo_path()
        # TODO: добавить защиту от некорректных параметров (mean_count > 0, не str и тд)

        path = base_path / folder / file
        if Path.exists(path):
            config = ConfigParser()
            config.read(str(path))
            for sec in config.sections():
                for key, value in config[sec].items():
                    setattr(Settings, key.upper(), float(value) if '.' in value else int(value))

    @staticmethod
    def save(folder: str = FOLDER, file: str = FILE):
        base_path = Settings.get_repo_path()

        config = ConfigParser()
        fields = {k: vars(Settings)[k] for k in vars(Settings) if k.isupper()}
        config['settings'] = fields
        path = base_path / folder
        Path.mkdir(path, exist_ok=True)
        with open(path / file, 'w') as file:
            config.write(file)


class SelectedArea:
    @staticmethod
    def load(folder: str = FOLDER, file: str = AREA_FILE):
        base_path = Settings.get_repo_path()

        path = base_path / folder / file
        if Path.exists(path):
            left_top, right_top, right_bottom, left_bottom = pickle.loads(Path.read_bytes(path))
            return left_top, right_top, right_bottom, left_bottom

    @staticmethod
    def save(points, folder: str = FOLDER, file: str = AREA_FILE):
        base_path = Settings.get_repo_path()
        path = base_path / folder

        Path.mkdir(path, exist_ok=True)
        with open(path / file, 'wb') as file:
            pickle.dump(tuple(points), file)
