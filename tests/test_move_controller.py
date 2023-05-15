from model.move_controller import MoveController
from common.coordinates import Point
from time import sleep
from common.settings import settings


def test_move_controller():
    settings.STABLE_POSITION_DURATION = 0.5
    controller = MoveController(debug_on=True)
    controller.set_new_position(Point(10, 10))
    # TODO: задействовать проверку таймера
    controller.set_new_position(Point(100, 100))
    assert controller._current_position == Point(100, 100)
    sleep(0.05)
    controller.set_new_position(Point(100, 100))
    assert controller._current_position == Point(100, 100)
