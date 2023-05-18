from itertools import repeat
from eye_tracker.common.coordinates import Point
from unittest.mock import Mock
from eye_tracker.model.selector import ObjectSelector, AreaSelector, MIN_DISTANCE_BETWEEN_POINTS
import pytest
from tests.fixtures import selected_object_points


def test_object_selector(selected_object_points, created_selector=None):
    callback = Mock(return_value=None)
    selector = created_selector or ObjectSelector('test_selector', callback)
    selector.draw_selected_rect = Mock(return_value=True)
    funcs = [selector.left_button_click, *repeat(selector.left_button_down_moved, 2), selector.left_button_up]
    for event, point in zip(funcs, selected_object_points):
        event(point)
    selector.finish_selecting()
    assert selector.is_done
    assert selector.left_top == Point(0, 0)
    assert selector.right_bottom == Point(MIN_DISTANCE_BETWEEN_POINTS, MIN_DISTANCE_BETWEEN_POINTS)
    return selector


def test_object_selector_swap_coordinates(selected_object_points):
    test_object_selector(selected_object_points[::-1])


@pytest.fixture
def selected_area_points():
    return [Point(0, 0), Point(MIN_DISTANCE_BETWEEN_POINTS, 0),
            Point(MIN_DISTANCE_BETWEEN_POINTS, MIN_DISTANCE_BETWEEN_POINTS),
            Point(0, MIN_DISTANCE_BETWEEN_POINTS)]


def test_area_selector(selected_area_points, created_selector=None):
    callback = Mock(return_value=None)
    selector = created_selector or AreaSelector('test_selector', callback)
    selector.draw_selected_rect = Mock(return_value=True)
    funcs = [*repeat(selector.left_button_click, 4)]
    for event, point in zip(funcs, selected_area_points):
        event(point)
    assert selector.is_done
    assert selector._points == selected_area_points
    return selector
