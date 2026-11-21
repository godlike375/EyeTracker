from time import time
from typing import Optional

from .interfaces import Notifier
from .laser_controller import (
    LaserConfig,
    COMMAND_MOVE,
    CALIBRATE_LASER_COMMAND,
)
from tracker.utils.coordinates import Point
from tracker.utils.threading import MutableValue, ThreadLoopable

DEFAULT_MOVE_DURATION = 0.4
DEFAULT_FRAME_MARGIN = 0.1


class VirtualLaserController:
    """Замена LaserController для работы без подключённого контроллера лазера.

    Полностью повторяет интерфейс LaserController, но вместо последовательного
    порта плавно интерполирует текущую позицию к заданной. Позиция выражается
    в координатах лазера (±max_laser_range).

    Дополнительно моделирует «физическое» положение пятна лазера на кадре через
    собственную (ground-truth) карту laser->screen (set_frame_size/laser_to_screen).
    Это позволяет отображать лазер без калибровки и проходить авто-калибровку
    без детекции пятна на камере.
    """

    def __init__(self,
                 notifier: Optional[Notifier] = None,
                 config: Optional[LaserConfig] = None,
                 move_duration: float = DEFAULT_MOVE_DURATION,
                 speed: Optional[float] = None,
                 fps: Optional[int] = None):
        self._notifier = notifier
        self._config = config or LaserConfig()
        self._on_laser_error = lambda: None

        self._move_duration = max(move_duration, 1e-3)
        self._last_tick = time()
        r = max(self._config.max_laser_range, 1)
        self._default_speed = (2 * r) / self._move_duration
        self._speed = float(speed) if speed else self._default_speed

        self._frame_width = None
        self._frame_height = None
        self._frame_margin = DEFAULT_FRAME_MARGIN

        self.laser_borders = [
            Point(-r, -r), Point(r, -r), Point(r, r), Point(-r, r)
        ]

        self._current_position = Point(0, 0)
        self._next_command_point = None
        self._stable_position_timer = 0.0
        self._ready = True
        self._errored = False
        self._initialized = True

        poll_fps = fps or self._config.poll_fps
        self._loop = ThreadLoopable(
            self._processing_loop,
            MutableValue(1 / max(poll_fps, 1)),
            run_immediately=False,
        )

    def set_on_laser_error(self, callback) -> None:
        self._on_laser_error = callback or (lambda: None)

    def start(self) -> None:
        self._loop.start_thread()

    def stop(self) -> None:
        self._loop.stop_thread()

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def set_frame_size(self, width: int, height: int, margin: float = DEFAULT_FRAME_MARGIN) -> None:
        self._frame_width = int(width)
        self._frame_height = int(height)
        self._frame_margin = margin

    def laser_to_screen(self, position: Point):
        if self._frame_width is None or self._frame_height is None:
            return None
        r = max(self._config.max_laser_range, 1)
        mx = self._frame_width * self._frame_margin
        my = self._frame_height * self._frame_margin
        sx = mx + (position.x + r) / (2 * r) * (self._frame_width - 2 * mx)
        sy = my + (position.y + r) / (2 * r) * (self._frame_height - 2 * my)
        return Point(int(sx), int(sy))

    def current_screen_point(self):
        return self.laser_to_screen(self._current_position)

    @property
    def is_stable_position(self) -> bool:
        return time() - self._stable_position_timer > self._config.stable_position_duration

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def is_errored(self) -> bool:
        return self._errored

    @property
    def current_position(self) -> Point:
        return self._current_position

    def _processing_loop(self):
        now = time()
        dt = now - self._last_tick
        self._last_tick = now
        if self._next_command_point is None:
            return

        target, command = self._next_command_point
        dx = target.x - self._current_position.x
        dy = target.y - self._current_position.y
        dist = (dx * dx + dy * dy) ** 0.5
        step = self._speed * dt

        if command == CALIBRATE_LASER_COMMAND and dist == 0:
            self._finish_move(target, now)
            return

        if dist <= step or dist == 0:
            self._finish_move(target, now)
            return

        self._current_position = Point(
            self._current_position.x + dx / dist * step,
            self._current_position.y + dy / dist * step,
        )

    def _finish_move(self, target: Point, now: float):
        self._current_position = target
        self._next_command_point = None
        self._stable_position_timer = now
        self._ready = True

    def set_new_position(self, position: Point) -> None:
        if position == self._current_position and self._next_command_point is None:
            return
        if self.is_errored:
            return
        if not self.is_stable_position:
            return
        if abs(position.x) > self._config.max_laser_range or \
                abs(position.y) > self._config.max_laser_range:
            return
        self._stable_position_timer = time()
        self._next_command_point = (position, COMMAND_MOVE)

    def set_speed(self, speed: Optional[float]) -> None:
        """Live-update the laser movement speed (calibration, moves and tracking)."""
        self._speed = float(speed) if speed else self._default_speed

    def track_position(self, position: Point) -> None:
        """Continuous smooth tracking: update the target without the settle gate."""
        if self.is_errored:
            return
        if abs(position.x) > self._config.max_laser_range or \
                abs(position.y) > self._config.max_laser_range:
            return
        self._ready = False
        self._next_command_point = (position, COMMAND_MOVE)

    def calibrate_laser(self) -> None:
        self._errored = False
        self.move_laser(0, 0, command=CALIBRATE_LASER_COMMAND)

    def center_laser(self) -> None:
        self.move_laser(0, 0)

    def move_laser(self, x, y, command: int = COMMAND_MOVE) -> None:
        if self.is_errored:
            return
        self._ready = False
        self._next_command_point = (Point(x, y), command)

    def controller_is_ready(self) -> bool:
        return self.is_stable_position and self.is_ready and self._next_command_point is None
