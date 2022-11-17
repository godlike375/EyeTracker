import pickle
from configparser import ConfigParser
from pathlib import Path

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
    FPS = 60  # target frames per second
    SERIAL_BAUND_RATE = 115200
    SERIAL_TIMEOUT = 0.01
    SERIAL_PORT = 8
    MEAN_TRACKING_COUNT = 3
    NOISE_THRESHOLD = 0.035
    MAX_RANGE = 6000
    STABLE_POSITION_DURATION = 0.67

    @staticmethod
    def get_repo_path(current: Path = None):
        if ROOT_DIR is not None:
            return Path(ROOT_DIR)
        current_path = current or Path.cwd()
        while current_path.name != ROOT_FOLDER:
            if current_path == current_path.parent:
                raise FileNotFoundError(f'Корневая директория программы "{ROOT_FOLDER}" не найдена')
            current_path = current_path.parent
        return current_path

    @staticmethod
    def load(folder: str = FOLDER, file: str = FILE):
        base_path = Settings.get_repo_path()

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
            left_top, right_bottom = pickle.loads(Path.read_bytes(path))
            return left_top, right_bottom

    @staticmethod
    def save(left_top, right_bottom, folder: str = FOLDER, file: str = AREA_FILE):
        base_path = Settings.get_repo_path()
        path = base_path / folder

        Path.mkdir(path, exist_ok=True)
        with open(path / file, 'wb') as file:
            pickle.dump((left_top, right_bottom), file)
