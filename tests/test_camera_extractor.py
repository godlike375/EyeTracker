from unittest.mock import Mock, patch
import pytest
from eye_tracker.common.settings import FLIP_SIDE_NONE, FLIP_SIDE_HORIZONTAL, FLIP_SIDE_VERTICAL
from eye_tracker.model import camera_extractor
from tests.fixtures import mocked_source_camera, black_frame


def patch_extractor(extractor, frame=None):
    extractor._camera = Mock()
    extractor._camera.read = frame or Mock(return_value=(Mock(), Mock()))


def test_extractor(mocked_source_camera):
    extractor = mocked_source_camera
    patch_extractor(extractor)
    extractor.extract_frame()
    assert extractor._camera.read.call_count > 0


def test_extractor_invalid_camera(mocked_source_camera):
    mock_show_error = Mock(return_value=None)
    camera_extractor.DEFAULT_CAMERA_ID = 5
    with patch("eye_tracker.view.view_output.show_error", mock_show_error):
        extractor = mocked_source_camera
        extractor.try_set_camera = Mock(return_value=False)
        extractor.set_source(4)
        assert mock_show_error.call_count == 1


def test_extractor_rotate(black_frame, mocked_source_camera):
    extractor = mocked_source_camera
    with pytest.raises(KeyError):
        extractor.set_frame_rotate(360)
        extractor.rotate_frame(black_frame)

    extractor.set_frame_rotate(90)
    extractor.set_frame_rotate(180)
    extractor.set_frame_rotate(270)
    extractor.rotate_frame(black_frame)


def test_extractor_flip(black_frame, mocked_source_camera):
    extractor = mocked_source_camera
    extractor.set_frame_flip('invalid')
    try:
        extractor.flip_frame(black_frame)
    except BaseException:
        assert True
    else:
        assert False
    extractor.set_frame_flip(FLIP_SIDE_NONE)
    extractor.set_frame_flip(FLIP_SIDE_HORIZONTAL)
    extractor.set_frame_flip(FLIP_SIDE_VERTICAL)
    extractor.flip_frame(black_frame)
