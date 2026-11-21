from enum import Enum
from typing import Protocol

from tracker.utils.coordinates import Point


class StatusMessage(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Notifier(Protocol):
    def notify(self, message: str, level: StatusMessage = StatusMessage.INFO) -> None:
        ...

    def show_error(self, message: str) -> None:
        ...

    def show_warning(self, message: str) -> None:
        ...


class LaserController(Protocol):
    def set_on_laser_error(self, callback) -> None:
        ...

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def set_new_position(self, position: Point) -> None:
        ...

    def move_laser(self, x: float, y: float) -> None:
        ...

    def calibrate_laser(self) -> None:
        ...

    def center_laser(self) -> None:
        ...

    def controller_is_ready(self) -> bool:
        ...

    @property
    def current_position(self) -> Point:
        ...

    @property
    def is_ready(self) -> bool:
        ...

    @property
    def is_errored(self) -> bool:
        ...

    @property
    def laser_borders(self) -> list[Point]:
        ...
