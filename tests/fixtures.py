import pytest
import numpy as np
from unittest.mock import Mock
from eye_tracker.model.domain_services import Orchestrator
from eye_tracker.model.camera_extractor import CameraService
from eye_tracker.model.selector import MIN_DISTANCE_BETWEEN_POINTS
from eye_tracker.common.coordinates import Point


@pytest.fixture
def mocked_source_camera():
    extractor = CameraService(auto_set=False)
    extractor.try_set_camera = Mock(return_value=True)
    return extractor


def fake_view_model():
    view_model = Mock()
    view_model.menu_state = []

    def set_tip(tip):
        view_model.tip = tip

    view_model.set_tip = set_tip

    def set_menu_state(category, state):
        view_model.menu_state.append((category, state))

    view_model.set_menu_state = set_menu_state
    return view_model


@pytest.fixture
def fake_model(mocked_source_camera):
    fake = Orchestrator(view_model=fake_view_model(), area=None, debug_on=True, run_immediately=False,
                        camera=mocked_source_camera, laser=Mock())
    fake._thread_loop = Mock()
    fake._thread_loop.stop = Mock(return_value=None)
    return fake


@pytest.fixture
def fake_area():
    area = Mock()
    area.is_empty = False
    return area


@pytest.fixture
def black_frame():
    return np.zeros((100, 100, 3), dtype=np.uint8)


@pytest.fixture
def selected_object_points():
    return [Point(0, 0), Point(1, 1), Point(2, 2), Point(MIN_DISTANCE_BETWEEN_POINTS, MIN_DISTANCE_BETWEEN_POINTS)]


@pytest.fixture
def selected_area_points():
    return [Point(0, 0), Point(MIN_DISTANCE_BETWEEN_POINTS, 0),
            Point(MIN_DISTANCE_BETWEEN_POINTS, MIN_DISTANCE_BETWEEN_POINTS),
            Point(0, MIN_DISTANCE_BETWEEN_POINTS)]


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


@pytest.fixture
def relative_coords():
    return (
        (Point(50, 50), Point(0, 0)),
        (Point(0, 0), Point(-100, -100)),
        (Point(100, 100), Point(100, 100)),
    )


@pytest.fixture
def intersected_coords():
    return (
        (Point(-10, -10), True),
        (Point(10, 10), False)
    )
