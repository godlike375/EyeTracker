from unittest.mock import Mock
from eye_tracker.model.frame_processing import Denoiser, Tracker
from eye_tracker.common.coordinates import Point
import numpy as np
from eye_tracker.common.settings import settings


def test_denoiser():
    denoiser = Denoiser(1, 3)
    denoiser.add(2)
    assert denoiser.get() >= 1.3 and denoiser.get() <= 1.4
    denoiser.add(-3)
    assert denoiser.get() == 0

def test_tracker_coordinates_calculation():
    tracker = Tracker()
    tracker.tracker = Mock()
    rect = Mock()
    settings.DOWNSCALE_FACTOR = 0.5
    rect.left = Mock(return_value=55 * settings.DOWNSCALE_FACTOR)
    rect.top = Mock(return_value=55 * settings.DOWNSCALE_FACTOR)
    rect.right = Mock(return_value=65 * settings.DOWNSCALE_FACTOR)
    rect.bottom = Mock(return_value=65 * settings.DOWNSCALE_FACTOR)
    tracker.tracker.get_position = Mock(return_value=rect)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    tracker.start_tracking(frame, Point(53, 53), Point(63, 63))
    coords = tracker.get_tracked_position(frame)
    assert coords == Point(58, 58)
    assert tracker.left_top == Point(53, 53)
    assert tracker.right_bottom == Point(63, 63)