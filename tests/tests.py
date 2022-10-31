from time import sleep
from unittest.mock import Mock
from itertools import repeat


import pytest

from common.utils import Point, ThreadLoopable
from model.frame_processing import Denoiser, FramePipeline
from model.frame_processing import Tracker
from model.settings import Settings
from model.selector import Selector


def test_denoiser():
    denoiser = Denoiser(1, 3)
    denoiser.add(2)
    assert denoiser.get() >= 1.3 and denoiser.get() <= 1.4
    denoiser.add(-3)
    assert denoiser.get() == 0


def test_process_with_pipeline():
    obj = Mock()

    def stage_A(obj):
        obj.A = True
        return obj

    def stage_B(obj):
        obj.B = True
        return obj

    def stage_C(obj):
        obj.C = True
        return obj

    pipeline = FramePipeline(stage_A, stage_B, stage_C)
    obj = pipeline.run_pure(obj)
    assert hasattr(obj, 'A') and obj.A
    assert hasattr(obj, 'B') and obj.B
    assert hasattr(obj, 'C') and obj.C


def test_load_valid_settings():
    extract_upper_fields = lambda d: {k: d[k] for k in d if k.isupper()}
    default = extract_upper_fields(vars(Settings))
    Settings.load(folder='tests', file='test_changed_config.ini')
    loaded = extract_upper_fields(vars(Settings))
    assert default != loaded
    assert loaded['MAX_RANGE'] == 5000


def test_save_and_load_settings():
    extract_upper_fields = lambda d: {k: d[k] for k in d if k.isupper()}
    default = extract_upper_fields(vars(Settings))
    Settings.save(folder='tests', file='test_saved_config.ini')
    Settings.load(folder='tests', file='test_saved_config.ini')
    assert default == extract_upper_fields(vars(Settings))


def test_thread_loopable():
    class Loopable(ThreadLoopable):
        def __init__(self):
            self.counter = 0
            super().__init__(self.loop, interval=0.000001)

        def loop(self):
            self.counter += 1

    loopable = Loopable()
    sleep(0.05)
    loopable.stop_thread()
    assert loopable.counter > 0


def test_tracker_coordinates_calculation():
    tracker = Tracker()
    tracker.tracker = Mock()
    rect = Mock()
    rect.left = Mock(return_value=1)
    rect.top = Mock(return_value=1)
    rect.right = Mock(return_value=11)
    rect.bottom = Mock(return_value=11)
    tracker.tracker.get_position = Mock(return_value=rect)
    frame = Mock()
    tracker.start_tracking(frame, Point(0, 0), Point(10, 10))
    coords = tracker.get_tracked_position(frame)
    assert coords == Point(5, 5)
    assert tracker.left_top == Point(0, 0)
    assert tracker.right_bottom == Point(10, 10)

@pytest.fixture
def selected_points():
    return [Point(i, i) for i in range(4)]

def test_selector(selected_points):
    pipeline = FramePipeline()
    callback = Mock(return_value=None)
    selector = Selector('test_selector', pipeline, callback)
    selector.draw_selected_rect = Mock(return_value=True)
    point = selected_points.__iter__()
    funcs = [selector.start, *repeat(selector.progress, 2), selector.end]
    for f in funcs:
        f(next(point))
        pipeline.run_pure(Mock())

    assert selector.is_selected()
    assert selector.draw_selected_rect.call_count == 4
    assert selector.left_top == Point(0, 0)
    assert selector.right_bottom == Point(3, 3)

def test_selector_swap_coordinates(selected_points):
    test_selector(sorted(selected_points, reverse=True))