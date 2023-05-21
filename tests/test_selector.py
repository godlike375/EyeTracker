from itertools import repeat
from eye_tracker.common.coordinates import Point
from unittest.mock import Mock
from eye_tracker.model.selector import ObjectSelector, AreaSelector, MIN_DISTANCE_BETWEEN_POINTS


def select_object_emulate(selected_object_points, created_selector=None):
    callback = Mock(return_value=None)
    selector = created_selector or ObjectSelector('test_selector', callback)
    selector.draw_selected_rect = Mock(return_value=True)
    funcs = [selector.left_button_click, *repeat(selector.left_button_down_moved, 2), selector.left_button_up]
    for event, point in zip(funcs, selected_object_points):
        event(point)
    selector.finish_selecting()
    return selector


def test_object_selection(selected_object_points):
    object = select_object_emulate(selected_object_points)
    assert object.is_done
    assert object.left_top == Point(0, 0)
    assert object.right_bottom == Point(MIN_DISTANCE_BETWEEN_POINTS, MIN_DISTANCE_BETWEEN_POINTS)
    return object

def test_object_selector_swap_coordinates(selected_object_points):
    select_object_emulate(selected_object_points[::-1])


def select_area_emulate(selected_area_points, created_selector=None):
    callback = Mock(return_value=None)
    selector = created_selector or AreaSelector('test_selector', callback)
    selector.draw_selected_rect = Mock(return_value=True)
    funcs = [*repeat(selector.left_button_click, 4)]
    for event, point in zip(funcs, selected_area_points):
        event(point)
    return selector


def test_area_selection(selected_area_points):
    area = select_area_emulate(selected_area_points)
    assert area.is_done
    assert area._points == selected_area_points
    return area

def test_area_selector_swap_coordinates(selected_area_points):
    select_area_emulate(selected_area_points[::-1])
