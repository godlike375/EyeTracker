from configparser import ConfigParser
from pathlib import Path

FOLDER = 'config'
FILE = 'eyetracker_settings.ini'
MAIN_ROOT_FOLDER = 'EyeTracker'

class Settings:
    CAMERA_ID = 1  # the second web-camera
    CAMERA_MAX_RESOLUTION = 800  # max height
    FPS = 60  # target frames per second
    SERIAL_BAUND_RATE = 115200
    SERIAL_TIMEOUT = 0.01
    SERIAL_PORT = 8
    MEAN_TRACKING_COUNT = 3
    NOISE_THRESHOLD = 0.035
    MAX_RANGE = 6000

    @staticmethod
    def get_repo_path():
        current = Path.cwd()
        while current.name != MAIN_ROOT_FOLDER:
            current = current.parent
        return current

    @staticmethod
    def load(folder: str=None, file: str=None):
        base_path = Settings.get_repo_path()
        folder = folder or FOLDER
        file = file or FILE

        path = base_path / folder / file
        if Path.exists(path):
            config = ConfigParser()
            config.read(str(path))
            for sec in config.sections():
                for field in config[sec]:
                    value = config[sec][field]
                    setattr(Settings, field.upper(), float(value) if '.' in value else int(value))

    @staticmethod
    def save(folder: str=None, file: str=None):
        base_path = Settings.get_repo_path()
        folder = folder or FOLDER
        file = file or FILE

        config = ConfigParser()
        fields = {k: vars(Settings)[k] for k in vars(Settings) if k.isupper()}
        config['settings'] = fields
        path = base_path / folder
        Path.mkdir(path, exist_ok=True)
        with open(path / file, 'w') as file:
            config.write(file)
