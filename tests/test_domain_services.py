from unittest.mock import Mock
from time import sleep

from eye_tracker.common.settings import settings, OBJECT, AREA
from eye_tracker.view.view_model import SELECTION_MENU_NAME
from eye_tracker.model.domain_services import ErrorHandler
from eye_tracker.common.settings import FLIP_SIDE_NONE, FLIP_SIDE_VERTICAL
from eye_tracker.common.coordinates import Point
from eye_tracker.model.move_controller import MoveController, SerialStub

from tests.test_selector import select_area_emulate, select_object_emulate


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
    thresh_calibrator.finish()
    thresh_calibrator._on_calibrated()
    assert view_model.menu_state == [(SELECTION_MENU_NAME, 'disabled'), ('all', 'normal'),
                                     (SELECTION_MENU_NAME, 'disabled'), (SELECTION_MENU_NAME, 'disabled')]
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
                                      (SELECTION_MENU_NAME, 'disabled'), ('all', 'normal')]
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


def test_flip_image_resets_area(fake_model, selected_area_points):
    area = fake_model.selecting.try_create_selector(AREA, reselect_while_calibrating=False, additional_callback=None)
    area._after_selection = Mock()
    select_area_emulate(selected_area_points, created_selector=area)
    selected, _ = fake_model.selecting.check_selected_correctly(AREA)

    fake_model.flip_image(FLIP_SIDE_NONE)
    assert fake_model.screen.selector_exists(AREA)

    fake_model.flip_image(FLIP_SIDE_VERTICAL)
    assert not fake_model.screen.selector_exists(AREA)


def test_rotate_image_resets_area(fake_model, selected_area_points):
    area = fake_model.selecting.try_create_selector(AREA, reselect_while_calibrating=False, additional_callback=None)
    area._after_selection = Mock()
    select_area_emulate(selected_area_points, created_selector=area)
    selected, _ = fake_model.selecting.check_selected_correctly(AREA)

    fake_model.rotate_image(0)
    assert fake_model.screen.selector_exists(AREA)

    fake_model.rotate_image(90)
    assert not fake_model.screen.selector_exists(AREA)


def test_noise_calibrate(fake_model, selected_object_points, black_frame):
    fake_model._current_frame = black_frame
    thresh_calibrator = fake_model.calibrators['noise threshold']
    fake_model.calibrate_noise_threshold()
    fake_model.selecting.try_create_selector(name=OBJECT, reselect_while_calibrating=True,
                                             additional_callback=thresh_calibrator.calibrate)
    assert fake_model.screen.selector_exists(OBJECT)
    object = fake_model.screen.get_selector(OBJECT)
    select_object_emulate(selected_object_points, object)
    settings._set_attr_force('THRESHOLD_CALIBRATION_DURATION', 3)
    sleep(1)
    fake_model.screen.get_selector(OBJECT)._center += Point(1, 1)
    while thresh_calibrator.in_progress:
        sleep(0.1)
    assert settings.NOISE_THRESHOLD_PERCENT == 0.0025


def test_coordinates_calibrate(fake_model, selected_object_points, black_frame, selected_area_points):
    fake_model._current_frame = black_frame
    fake_model.laser = MoveController(Mock())
    SerialStub.READY_INTERVAL = 1.1
    coordinate_calibrator = fake_model.calibrators['coordinate system']
    fake_model.calibrate_coordinate_system()
    fake_model.selecting.try_create_selector(name=OBJECT, reselect_while_calibrating=True,
                                             additional_callback=coordinate_calibrator.calibrate)
    assert fake_model.screen.selector_exists(OBJECT)
    object = fake_model.screen.get_selector(OBJECT)

    MAX_LASER_RANGE = settings.MAX_LASER_RANGE_PLUS_MINUS
    left_top = Point(-MAX_LASER_RANGE, -MAX_LASER_RANGE)
    right_top = Point(MAX_LASER_RANGE, -MAX_LASER_RANGE)
    right_bottom = Point(MAX_LASER_RANGE, MAX_LASER_RANGE)
    left_bottom = Point(-MAX_LASER_RANGE, MAX_LASER_RANGE)
    coordinate_calibrator._laser_borders = [left_top, right_top, right_bottom, left_bottom]

    select_object_emulate(selected_object_points, object)
    sleep(0.15)
    current_point = iter(selected_area_points)
    while coordinate_calibrator.in_progress:
        sleep(1)
        if fake_model.screen.selector_exists(OBJECT):
            fake_model.screen.get_selector(OBJECT)._center = next(current_point)
    assert fake_model.screen.selector_exists(AREA)
    fake_model.laser.stop_thread()
