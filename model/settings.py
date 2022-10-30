from configparser import ConfigParser
from pathlib import Path

FOLDER = 'config'
FILE = 'eyetracker_settings.ini'
RUNTIME_CALCULATED_SETTINGS = ['INTERVAL']


class Settings:
    CAMERA_ID = 1  # the second web-camera
    CAMERA_MAX_RESOLUTION = 800 # max height
    FPS = 60  # target frames per second
    SERIAL_BAUND_RATE = 115200
    SERIAL_TIMEOUT = 0.01
    SERIAL_PORT = 8
    MEAN_TRACKING_COUNT = 3
    NOISE_THRESHOLD = 0.035

    MAX_RANGE = 6000


    @staticmethod
    def load():
        path = Path.cwd() / FOLDER / FILE
        if Path.exists(path):
            config = ConfigParser()
            config.read(str(path))
            for sec in config.sections():
                for field in config[sec]:
                    value = config[sec][field]
                    setattr(Settings, field.upper(), float(value) if '.' in value else int(value))
        Settings.INTERVAL = 1 / Settings.FPS

    @staticmethod
    def save():
        config = ConfigParser()
        fields = {k:vars(Settings)[k] for k in vars(Settings) if k.isupper() and k not in RUNTIME_CALCULATED_SETTINGS}
        config['settings'] = fields
        path = Path.cwd() / FOLDER
        Path.mkdir(path, exist_ok=True)
        with open(path / FILE, 'w') as file:
            config.write(file)