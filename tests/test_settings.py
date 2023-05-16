from unittest.mock import Mock, patch, mock_open

import pytest

from model.common.settings import settings


@pytest.fixture
def test_config_ini():
    return """
[settings]
camera_id = 5
camera_max_height_resolution = 640
fps_viewed = 19
fps_processed = 76
serial_baud_rate = 115200
serial_timeout = 0.01
serial_port = 1
mean_coordinates_frame_count = 2
noise_threshold_percent = 0.0
threshold_calibration_duration = 8
stable_position_duration = 0.67
max_laser_range_plus_minus = 6000
downscale_factor = 0.25
same_frames_threshold = 0.53
        """


def load_mock_config(test_config_ini):
    with patch("builtins.open", mock_open(read_data=test_config_ini)):
        with patch("pathlib.Path.exists", Mock(return_value=True)):
            settings.load('', '')


def test_load_valid_settings(test_config_ini):
    extract_upper_fields = lambda d: {k: d[k] for k in d if k.isupper()}
    default = extract_upper_fields(vars(settings))
    load_mock_config(test_config_ini)
    loaded = extract_upper_fields(vars(settings))
    assert default != loaded
    assert loaded['MAX_LASER_RANGE_PLUS_MINUS'] == 6000
    assert loaded['SAME_FRAMES_THRESHOLD'] == 0.53
    assert loaded['CAMERA_ID'] == 5


def test_save_and_load_settings():
    extract_upper_fields = lambda d: {k: d[k] for k in d if k.isupper()}
    default = extract_upper_fields(vars(settings))
    settings.save(file='test_saved_config.ini')
    settings.load(file='test_saved_config.ini')
    assert default == extract_upper_fields(vars(settings))
