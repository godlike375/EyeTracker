from unittest.mock import Mock

from eye_tracker.common.settings import settings, OBJECT, AREA
from eye_tracker.view.view_model import SELECTION_MENU_NAME
from eye_tracker.model.domain_services import ErrorHandler


def test_restart_after_multiple_errors(fake_model):
    view_model = fake_model._view_model

    def break_model_loop_from_inside():
        raise Exception

    ErrorHandler.RESTART_IN_TIME_SEC = 1
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


def test_cancel_active_process(fake_model):
    area = fake_model.selecting.try_create_selector(AREA, reselect_while_calibrating=False, additional_callback=None)
    area._after_selection = Mock()
    area.start()
    assert fake_model.screen.selector_exists(AREA)
    fake_model.cancel_active_process(need_confirm=False)
    assert not fake_model.screen.selector_exists(AREA)
