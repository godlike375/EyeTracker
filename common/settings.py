import pickle
from abc import ABC, abstractmethod
from configparser import ConfigParser
from pathlib import Path
from sys import maxsize

from common.logger import logger
from view import view_output

AREA = 'area'
OBJECT = 'object'
TRACKER = 'tracker'
FOLDER = 'config'
FILE = 'eyetracker_settings.ini'
AREA_FILE = 'selected_area.pickle'
ROOT_FOLDER = 'EyeTracker'
ROOT_DIR = None
INFINITE = maxsize

INTERGER_TYPE_ERROR = 'The value should be integer'


class Limitation(ABC):
    def __init__(self, limit_type):
        self._limit_type = limit_type

    @abstractmethod
    def satisfies_limitation(self, value): ...

    @abstractmethod
    def print_value(self, value): ...

    def print_type(self):
        return f'{self._limit_type}'

    def satisfies_type(self, value):
        return type(value) is self._limit_type


class OptionList(Limitation):
    def __init__(self, options: list):
        super().__init__(type(options[0]))
        self._options = options

    def satisfies_limitation(self, value):
        return value in self._options

    def print_value(self, value):
        return f'{value} должно быть одним из {self._options} '


class Range(Limitation):
    def __init__(self, min, max):
        super().__init__(type(min))
        self._min = min
        self._max = max

    def satisfies_limitation(self, value):
        return self._min <= value and value <= self._max

    def print_value(self, value):
        return f'{self._min} < {value} < {self._max}'


LIMITATIONS = {
    'CAMERA_ID': Range(0, INFINITE),
    'CAMERA_MAX_HEIGHT_RESOLUTION': Range(640, 640),
    # TODO: теоретически, можно здесь менять параметр, но даунскейлить потом до 640, чтобы красиво выводилось
    'FPS_VIEWED': Range(8, INFINITE),
    'FPS_PROCESSED': Range(32, INFINITE),
    'SERIAL_BAUD_RATE': OptionList([110, 300, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]),
    'SERIAL_TIMEOUT': Range(0.01, INFINITE),
    'SERIAL_PORT': Range(0, INFINITE),
    'TRACKING_FRAMES_MEAN_NUMBER': Range(1, 5),
    'NOISE_THRESHOLD_PERCENT': Range(0.0, INFINITE),
    'OBJECT_NOT_MOVING_DURATION': Range(4, 20),
    'STABLE_POSITION_DURATION': Range(0.5, 1.0),
    'MAX_LASER_RANGE_PLUS_MINUS': Range(1, INFINITE),
    'DOWNSCALE_FACTOR': Range(0.05, 0.5)
}


class Settings:

    def __init__(self):
        self.CAMERA_ID = 0
        self.CAMERA_MAX_HEIGHT_RESOLUTION = 640
        self.FPS_VIEWED = 25
        self.FPS_PROCESSED = 64
        self.SERIAL_BAUD_RATE = 115200
        self.SERIAL_TIMEOUT = 0.01
        self.SERIAL_PORT = 1
        self.TRACKING_FRAMES_MEAN_NUMBER = 2
        self.NOISE_THRESHOLD_PERCENT = 0.0
        self.OBJECT_NOT_MOVING_DURATION = 8  # в секундах
        self.STABLE_POSITION_DURATION = 0.67
        self.MAX_LASER_RANGE_PLUS_MINUS = 6000  # меняется в согласовании с аппаратной частью
        self.DOWNSCALE_FACTOR = 0.2

    def __setattr__(self, key, value):
        try:
            if key not in LIMITATIONS:
                raise KeyError(f'Параметр {key} не найден в списке доступных параметров. Он будет проигнорирован.')
            limitation = LIMITATIONS[key]
            if not limitation.satisfies_type(value):
                raise TypeError(f'Значение параметра {key} должно иметь тип {limitation.print_type()}')
            if not limitation.satisfies_limitation(value):
                raise ValueError(
                    f'Значение параметра  {key} должно удовлетворять условиям {limitation.print_value(value)}')
            super().__setattr__(key, value)
        except Exception as e:
            view_output.show_warning(e)

    @staticmethod
    def get_repo_path(current: Path = None):
        current_path = current or Path.cwd()
        while current_path.name != ROOT_FOLDER:
            if current_path == current_path.parent:
                if ROOT_DIR is not None:
                    return Path(ROOT_DIR)
                warning = f'Корневая директория программы "{ROOT_FOLDER}" не найдена'
                view_output.show_warning(warning)
                logger.log(warning)
                return Path.cwd()
            current_path = current_path.parent
        return current_path

    def load(self, folder: str = FOLDER, file: str = FILE):
        base_path = self.get_repo_path()

        path = base_path / folder / file
        if Path.exists(path):
            config = ConfigParser()
            config.read(str(path))
            for sec in config.sections():
                for key, value in config[sec].items():
                    setattr(self, key.upper(), float(value) if '.' in value else int(value))

    def save(self, folder: str = FOLDER, file: str = FILE):
        base_path = self.get_repo_path()

        config = ConfigParser()
        fields = {k: vars(self)[k] for k in vars(self) if k.isupper()}
        config['settings'] = fields
        path = base_path / folder
        Path.mkdir(path, exist_ok=True)
        with open(path / file, 'w') as file:
            config.write(file)


settings = Settings()


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
