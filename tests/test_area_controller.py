from model.area_controller import AreaController
from model.common.coordinates import Point
from unittest.mock import Mock
import pytest

@pytest.fixture
def relative_coords():
    return (
        (Point(50, 50), Point(0, 0)),
        (Point(0, 0), Point(-100, -100)),
        (Point(100, 100), Point(100, 100)),
    )


@pytest.fixture
def intersected_coords():
    return (
        (Point(-10, -10), True),
        (Point(10, 10), False)
    )

def test_area_controller(relative_coords, intersected_coords):
    controller = AreaController(-100, 100)
    area = Mock()
    area.points = [Point(0, 0), Point(100, 0), Point(100, 100), Point(0, 100)]
    laser_borders = [Point(-100, -100), Point(100, -100), Point(100, 100), Point(-100, 100)]
    controller.set_area(area, laser_borders)
    for coord_set in relative_coords:
        assert controller.calc_laser_coords(coord_set[0]) == coord_set[1]
    for coord_set in intersected_coords:
        assert controller.point_is_out_of_area(coord_set[0], beep_sound_allowed=False) == coord_set[1]