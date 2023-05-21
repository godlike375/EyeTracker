from unittest.mock import Mock, patch

from eye_tracker.common.settings import AREA, OBJECT

from tests.test_selector import select_object_emulate, select_area_emulate


def test_select_area_and_object(fake_model, selected_object_points, selected_area_points):
    model = fake_model

    area = model.selecting.try_create_selector(AREA, reselect_while_calibrating=False, additional_callback=None)
    area._after_selection = Mock()
    select_area_emulate(selected_area_points, created_selector=area)
    assert area is not None
    selected, _ = fake_model.selecting.check_selected_correctly(AREA)
    assert selected

    object = model.selecting.try_create_selector(OBJECT, reselect_while_calibrating=False, additional_callback=None)
    object._after_selection = Mock()
    select_object_emulate(selected_object_points, created_selector=object)
    assert object is not None
    selected, _ = fake_model.selecting.check_selected_correctly(OBJECT)
    assert selected

    with patch('eye_tracker.view.view_output.ask_confirmation', Mock(return_value=False)):
        object = model.selecting.try_create_selector(OBJECT, reselect_while_calibrating=False, additional_callback=None)
        assert object is None

    with patch('eye_tracker.view.view_output.ask_confirmation', Mock(return_value=True)):
        object = model.selecting.try_create_selector(OBJECT, reselect_while_calibrating=False, additional_callback=None)
        assert object is not None

    area = model.selecting.try_create_selector(AREA, reselect_while_calibrating=False, additional_callback=None)
    assert area is not None


def test_not_selected(fake_model):
    screen = fake_model.screen
    selecting = fake_model.selecting

    selecting.create_selector(AREA)
    assert screen.selector_exists(AREA)
    selected, _ = selecting.check_selected_correctly(AREA)
    assert not selected

    selecting.create_selector(OBJECT)
    assert screen.selector_exists(OBJECT)
    selected, _ = selecting.check_selected_correctly(OBJECT)
    assert not selected
