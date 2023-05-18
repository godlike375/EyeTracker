import pytest
from unittest.mock import Mock

from model.common.settings import settings, OBJECT
from view.view_model import SELECTION_MENU_NAME
from model.common.coordinates import Point
from tests.test_camera_extractor import mocked_source_camera
from model.domain_services import Orchestrator


@pytest.fixture
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
def fake_model(mocked_source_camera, fake_view_model):
    fake = Orchestrator(view_model=fake_view_model, area=None, debug_on=True, run_immediately=False, camera=mocked_source_camera,
                        laser=Mock())
    fake._thread_loop = Mock()
    fake._thread_loop.stop = Mock(return_value=None)
    return fake

# TODO: self._view_model.set_menu_state('all', 'disabled') протестировать вызовы в модели

@pytest.fixture
def fake_area():
    area = Mock()
    area.is_empty = False
    return area


def test_restart_after_multiple_errors(fake_model):
    view_model = fake_model._view_model
    def break_model_loop_from_inside():
        raise Exception
    from model import domain_services
    domain_services.RESTART_IN_TIME_SEC = 1
    fake_model.camera.extract_frame = break_model_loop_from_inside
    fake_model._processing_loop()
    fake_model._processing_loop()
    fake_model._processing_loop()
    assert 'Перезапуск программы будет произведён через 1 секунд' in view_model.tip

def test_correct_tip_switch(fake_model, fake_area):
    view_model = fake_model._view_model

    assert view_model.tip == 'Откалибруйте шумоподавление'

    settings.THRESHOLD_CALIBRATION_DURATION = 0

    fake_model.calibrate_noise_threshold()
    fake_model.calibrators['noise threshold']._on_calibrated()
    assert view_model.tip == 'Откалибруйте координатную систему или выделите область вручную'


    fake_model.area_controller.set_area = Mock()
    coord_calibrator = fake_model.calibrators['coordinate system']
    coord_calibrator._area = fake_area
    fake_model.selecting.check_selected_correctly = Mock(return_value=(True, fake_area))

    fake_model.calibrate_coordinate_system()
    coord_calibrator._on_calibrated()
    fake_model._on_area_selected()
    assert view_model.tip == 'Выделите объект слежения'

def test_correct_menu_items_hidden(fake_model, fake_area):
    view_model = fake_model._view_model
    assert view_model.menu_state == [('all', 'normal'), (SELECTION_MENU_NAME, 'disabled'),
                                     (SELECTION_MENU_NAME, 'disabled'), (SELECTION_MENU_NAME, 'disabled')]
    view_model.menu_state.clear()

    fake_model.calibrate_laser()
    assert view_model.menu_state == [(SELECTION_MENU_NAME, 'disabled')]
    view_model.menu_state.clear()

    settings.THRESHOLD_CALIBRATION_DURATION = 0

    thresh_calibrator = fake_model.calibrators['noise threshold']
    fake_model.calibrate_noise_threshold()
    fake_model.selecting.try_create_selector(name=OBJECT, reselect_while_calibrating=True,
                                             additional_callback=thresh_calibrator.calibrate)
    assert view_model.menu_state == [(SELECTION_MENU_NAME, 'disabled'), ('all', 'disabled')]
    view_model.menu_state.clear()

    thresh_calibrator._on_calibrated()
    assert view_model.menu_state == [(SELECTION_MENU_NAME, 'disabled'), (SELECTION_MENU_NAME, 'disabled'),
                                     (SELECTION_MENU_NAME, 'disabled'), ('all', 'normal')]
    view_model.menu_state.clear()

    fake_model.area_controller.set_area = Mock()
    coord_calibrator = fake_model.calibrators['coordinate system']
    coord_calibrator._area = fake_area
    fake_model.selecting.check_selected_correctly = Mock(return_value=(True, fake_area))

    fake_model.calibrate_coordinate_system()
    fake_model.selecting.try_create_selector(name=OBJECT, reselect_while_calibrating=True,
                                             additional_callback=coord_calibrator.calibrate)
    assert view_model.menu_state == [(SELECTION_MENU_NAME, 'disabled'), ('all', 'disabled')]
    view_model.menu_state.clear()

    coord_calibrator._on_calibrated()
    assert view_model.menu_state == [(SELECTION_MENU_NAME, 'disabled'), (SELECTION_MENU_NAME, 'disabled'),
                                     ('all', 'normal'), (SELECTION_MENU_NAME, 'disabled')]
    view_model.menu_state.clear()

    fake_model._on_area_selected()
    assert view_model.menu_state == [('all', 'normal'), (SELECTION_MENU_NAME, 'disabled')]
    view_model.menu_state.clear()