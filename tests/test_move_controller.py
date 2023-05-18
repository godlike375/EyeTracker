from eye_tracker.model.move_controller import MoveController
from eye_tracker.common.coordinates import Point
from time import sleep
from eye_tracker.common.settings import settings


def test_move_controller():

    settings._set_attr_force('STABLE_POSITION_DURATION', 0.005)
    with MoveController(on_laser_error=lambda : ..., debug_on=True, run_immediately=False) as controller:
        controller.set_new_position(Point(10, 10))
        controller.set_new_position(Point(100, 100))
        assert controller._current_position == Point(10, 10)

        sleep(0.006)
        controller.set_new_position(Point(200, 200))
        assert controller._current_position == Point(200, 200)
