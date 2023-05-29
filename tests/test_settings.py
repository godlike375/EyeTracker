from unittest.mock import Mock, patch, mock_open

from eye_tracker.common.settings import settings


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
    assert loaded['SAME_FRAMES_THRESHOLD'] == 0.53
    assert loaded['CAMERA_ID'] == 5


def test_save_and_load_settings():
    extract_upper_fields = lambda d: {k: d[k] for k in d if k.isupper()}
    default = extract_upper_fields(vars(settings))
    settings.save(file='test_saved_config.ini')
    settings.reset()
    settings.load(file='test_saved_config.ini')
    assert default == extract_upper_fields(vars(settings))
