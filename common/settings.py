import pickle
import sys
from abc import ABC, abstractmethod
from configparser import ConfigParser
from os import remove
from os.path import exists
from pathlib import Path
from sys import maxsize

from view import view_output

RESOLUTIONS = {1280: 720, 800: 600, 640: 480}
DOWNSCALED_HEIGHT = 640

AREA = 'area'
OBJECT = 'object'
TRACKER = 'tracker'
FOLDER = 'config'
FILE = 'eyetracker_settings.ini'
PRIVATE_FILE = 'private_settings.ini'
AREA_FILE = 'selected_area.pickle'
ROOT_FOLDER = 'EyeTracker'
ROOT_DIR = None
INFINITE = maxsize
FLIP_SIDE_NONE = -1
FLIP_SIDE_VERTICAL = 0
FLIP_SIDE_HORIZONTAL = 1

INTERGER_TYPE_ERROR = 'The value should be integer'
PARAMETER_NOT_APPLIED = 'Параметр не будет применён.'


def get_repo_path(bundled=False):
    if bundled and getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
        # запуск из PyInstaller bundle
        # создаётся в C:/Temp/_MEI... и туда закидываются все файлы, которые есть в режиме не onefile
    return Path.cwd()


class Limitation(ABC):
    def __init__(self, limit_type):
        self._limit_type = limit_type

    @abstractmethod
    def satisfies_limitation(self, value): ...

    @abstractmethod
    def print_value(self, value): ...

    def print_type(self):
        human_readable_type = 'целым'
        if self._limit_type is type(float):
            human_readable_type = 'нецелым'
        return f'{human_readable_type}'

    def satisfies_type(self, value):
        return type(value) is self._limit_type


class OptionList(Limitation):
    def __init__(self, *options):
        super().__init__(type(options[0]))
        self._options = list(options)

    def satisfies_limitation(self, value):
        return value in self._options

    def print_value(self, value):
        return f'{value} должно быть одним из {self._options}'


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
    'CAMERA_MAX_HEIGHT_RESOLUTION': OptionList(640, 800, 1280),
    'FPS_VIEWED': Range(8, INFINITE),
    'FPS_PROCESSED': Range(32, INFINITE),
    'SERIAL_BAUD_RATE': OptionList(110, 300, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200),
    'SERIAL_TIMEOUT': Range(0.01, INFINITE),
    'SERIAL_PORT': Range(0, INFINITE),
    'TRACKING_FRAMES_MEAN_NUMBER': Range(1, 5),
    'NOISE_THRESHOLD_PERCENT': Range(0.0, 1.0),
    'OBJECT_NOT_MOVING_DURATION': Range(4, 20),
    'STABLE_POSITION_DURATION': Range(0.5, 1.0),
    'MAX_LASER_RANGE_PLUS_MINUS': Range(1, INFINITE),
    'DOWNSCALE_FACTOR': Range(0.05, 0.5),
    'SAME_FRAMES_THRESHOLD': Range(0.01, 0.99),
    'ROTATION_ANGLE': OptionList(0, 90, 180, 270),
    'FLIP_SIDE': OptionList(FLIP_SIDE_NONE, FLIP_SIDE_HORIZONTAL, FLIP_SIDE_VERTICAL),
    'PAINT_COLOR_R': Range(0, 255),
    'PAINT_COLOR_G': Range(0, 255),
    'PAINT_COLOR_B': Range(0, 255)
}


class Settings:

    def __init__(self):
        self.CAMERA_ID = 0
        self.CAMERA_MAX_HEIGHT_RESOLUTION = 640
        self.FPS_VIEWED = 19
        self.FPS_PROCESSED = 76
        self.SERIAL_BAUD_RATE = 115200
        self.SERIAL_TIMEOUT = 0.01
        self.SERIAL_PORT = 1
        self.TRACKING_FRAMES_MEAN_NUMBER = 2
        self.NOISE_THRESHOLD_PERCENT = 0.0
        self.OBJECT_NOT_MOVING_DURATION = 8  # в секундах
        self.STABLE_POSITION_DURATION = 0.67
        self.MAX_LASER_RANGE_PLUS_MINUS = 6000  # меняется в согласовании с аппаратной частью
        self.DOWNSCALE_FACTOR = 0.25  # чем ниже значение, тем выше производительность, но ниже точность трекинга
        self.SAME_FRAMES_THRESHOLD = 0.53  # в полной темноте начиная с такого значения обновляется картинка

    def __setattr__(self, key, value):
        try:
            if key not in LIMITATIONS:
                raise KeyError(f'Параметр {key} не найден в списке доступных параметров. Он будет проигнорирован.')
            limitation = LIMITATIONS[key]
            if not limitation.satisfies_type(value):
                raise TypeError(f'Значение параметра {key} должно быть {limitation.print_type()}.'
                                f' {PARAMETER_NOT_APPLIED}')
            if not limitation.satisfies_limitation(value):
                raise ValueError(
                    f'Значение параметра  {key} должно удовлетворять условиям: {limitation.print_value(value)}.'
                    f' {PARAMETER_NOT_APPLIED}')

            super().__setattr__(key, value)
        except Exception as e:
            view_output.show_error(e)
            return False
        else:
            return True

    def load(self, folder: str = FOLDER, file: str = FILE):
        base_path = get_repo_path()

        path = base_path / folder / file
        if Path.exists(path):
            config = ConfigParser()
            config.read(str(path))
            for sec in config.sections():
                for key, value in config[sec].items():
                    self.__setattr__(key.upper(), float(value) if '.' in value else int(value))

    def save(self, folder: str = FOLDER, file: str = FILE):
        base_path = get_repo_path()

        config = ConfigParser()
        fields = {k: vars(self)[k] for k in vars(self) if k.isupper()}
        config['settings'] = fields
        path = base_path / folder
        Path.mkdir(path, exist_ok=True)
        with open(path / file, 'w') as file:
            config.write(file)

    def reset(self):
        self.__init__()


class PrivateSettings(Settings):
    def __init__(self):
        self.FLIP_SIDE = FLIP_SIDE_NONE
        self.ROTATION_ANGLE = 0
        self.PAINT_COLOR_R = 0
        self.PAINT_COLOR_G = 255
        self.PAINT_COLOR_B = 0

    def load(self, folder: str = FOLDER, file: str = None):
        file = file or PRIVATE_FILE
        super().load(file=file)

    def save(self, folder: str = FOLDER, file: str = None):
        file = file or PRIVATE_FILE
        super().save(file=file)


settings = Settings()
private_settings = PrivateSettings()


class SelectedArea:
    @staticmethod
    def load(folder: str = FOLDER, file: str = AREA_FILE):
        base_path = get_repo_path()

        path = base_path / folder / file
        if Path.exists(path):
            left_top, right_top, right_bottom, left_bottom = pickle.loads(Path.read_bytes(path))
            return left_top, right_top, right_bottom, left_bottom

    @staticmethod
    def save(points, folder: str = FOLDER, file: str = AREA_FILE):
        base_path = get_repo_path()
        path = base_path / folder

        Path.mkdir(path, exist_ok=True)
        with open(path / file, 'wb') as file:
            pickle.dump(tuple(points), file)

    @staticmethod
    def remove(folder: str = FOLDER, file: str = AREA_FILE):
        base_path = get_repo_path()
        path = base_path / folder / file
        if exists(path):
            remove(path)


MIN_THROTTLE_DIFFERENCE = 1.5
CALIBRATE = 2
