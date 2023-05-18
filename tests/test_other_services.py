from unittest.mock import Mock, patch

from model.common.settings import AREA, OBJECT

from tests.test_selector import test_object_selector, selected_object_points
from tests.test_domain_services import fake_model, mocked_source_camera, fake_view_model


def test_model_select(fake_model, selected_object_points):
    model = fake_model

    object = model.selecting.try_create_selector(OBJECT, reselect_while_calibrating=False, additional_callback=None)
    object._after_selection = Mock()
    test_object_selector(selected_object_points, created_selector=object)
    assert object is not None

    with patch('view.view_output.ask_confirmation', Mock(return_value=False)):
        object = model.selecting.try_create_selector(OBJECT, reselect_while_calibrating=False, additional_callback=None)
        assert object is None

    with patch('view.view_output.ask_confirmation', Mock(return_value=True)):
        object = model.selecting.try_create_selector(OBJECT, reselect_while_calibrating=False, additional_callback=None)
        assert object is not None

    area = model.selecting.try_create_selector(AREA, reselect_while_calibrating=False, additional_callback=None)
    assert area is not None
