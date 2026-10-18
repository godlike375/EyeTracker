from dataclasses import dataclass
from time import time
from typing import Optional

from serial import Serial, SerialException
from serial.tools import list_ports

from .interfaces import Notifier
from tracker.utils.coordinates import Point
from tracker.utils.logger import logger
from tracker.utils.threading import MutableValue, ThreadLoopable

READY = 'ready'
ERRORED = 'error'
LASER_DEVICE_NAME = 'usb-serial ch340'
COMMAND_MOVE = 1
CALIBRATE_LASER_COMMAND = 2
DEFAULT_BAUD_RATE = 19200
SERIAL_TIMEOUT = 0.1
DEFAULT_MAX_LASER_RANGE = 6000
DEFAULT_STABLE_POSITION_DURATION = 0.67
DEFAULT_POLL_FPS = 45


@dataclass
class LaserConfig:
    serial_port: int = 1
    baud_rate: int = DEFAULT_BAUD_RATE
    stable_position_duration: float = DEFAULT_STABLE_POSITION_DURATION
    max_laser_range: int = DEFAULT_MAX_LASER_RANGE
    poll_fps: int = DEFAULT_POLL_FPS

    @classmethod
    def from_settings(cls, settings) -> 'LaserConfig':
        return cls(
            serial_port=int(settings.serial_port),
            baud_rate=int(settings.baud_rate),
            stable_position_duration=float(settings.stable_position_duration),
            max_laser_range=int(settings.max_laser_range),
            poll_fps=int(settings.detector_fps),
        )


class LaserController:
    def __init__(self, notifier: Optional[Notifier] = None,
                 config: Optional[LaserConfig] = None,
                 debug_on: bool = False,
                 port_name: Optional[str] = None):
        self._notifier = notifier
        self._config = config or LaserConfig()
        self._on_laser_error = lambda: None

        self._initialized = False
        self._stable_position_timer = 0.0
        self._current_position = Point(0, 0)
        self._ready = False
        self._errored = False
        self._next_command_point = None
        self._serial = SerialStub()

        r = self._config.max_laser_range
        self.laser_borders = [
            Point(-r, -r), Point(r, -r), Point(r, r), Point(-r, r)
        ]

        self._loop = ThreadLoopable(
            self._processing_loop,
            MutableValue(1 / max(self._config.poll_fps, 1)),
            run_immediately=False,
        )

        if debug_on:
            self._notify_warning('Последовательный порт используется в режиме отладки')
            self._initialized = True
            return

        self._initialized = self._open_serial(port_name)

    def _open_serial(self, port_name: Optional[str]) -> bool:
        manual_port = port_name or f'COM{self._config.serial_port}'
        try:
            ports_names = {p.name: p.description.lower() for p in list_ports.comports()}
            ports_descriptions = {p.description.lower(): p.name for p in list_ports.comports()}
            if manual_port not in ports_names or ports_names[manual_port] != LASER_DEVICE_NAME:
                matching = [d for d in ports_descriptions if LASER_DEVICE_NAME in d]
                if not matching:
                    self._notify_error(
                        f'Не удалось открыть заданный настройкой порт {manual_port}, '
                        f'и не удалось определить подходящий порт автоматически. '
                        f'Программа продолжит работать без контроллера лазера.')
                    return False
                manual_port = ports_descriptions[matching[0]]
            self._serial = Serial(manual_port, self._config.baud_rate, timeout=SERIAL_TIMEOUT)
        except SerialException:
            logger.exception('Cannot open the proper serial port')
            return False
        return True

    def set_on_laser_error(self, callback) -> None:
        self._on_laser_error = callback or (lambda: None)

    def start(self) -> None:
        self._loop.start_thread()

    def stop(self) -> None:
        self._loop.stop_thread()

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def _processing_loop(self):
        serial_data = self._serial.readline()
        new_errored = self._errored or ERRORED in str(serial_data)
        self._ready = self._ready or READY in str(serial_data)

        if new_errored and self._errored != new_errored:
            self._notify_error(
                'Контроллер лазера внезапно дошёл до предельных координат.\n'
                'Необходимо откалибровать контроллер лазера повторно. '
                'До этого момента слежение за объектом невозможно')
            self._errored = new_errored
            self._on_laser_error()
            return

        if self._next_command_point is None:
            return

        if self.is_errored and self._next_command_point[1] != CALIBRATE_LASER_COMMAND:
            return

        if not self.is_ready:
            return

        if not self.is_stable_position:
            return

        self._move_laser(*self._next_command_point)
        self._stable_position_timer = time()
        self._ready = False
        self._next_command_point = None

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

    def _move_laser(self, position: Point, command: int = COMMAND_MOVE):
        message = (f'{int(position.x)};{int(position.y)};{command}\n').encode('ascii', 'ignore')
        self._serial.write(message)

    def set_new_position(self, position: Point) -> None:
        if position == self._current_position:
            return
        if self.is_errored:
            return
        if not self.is_stable_position:
            return
        if abs(position.x) > self._config.max_laser_range or \
                abs(position.y) > self._config.max_laser_range:
            logger.debug("can't set out of laser range position")
            return
        self._stable_position_timer = time()
        self._current_position = position
        self._next_command_point = (position, COMMAND_MOVE)

    def calibrate_laser(self) -> None:
        logger.debug('laser calibrated')
        self._errored = False
        self.move_laser(0, 0, command=CALIBRATE_LASER_COMMAND)

    def center_laser(self) -> None:
        logger.debug('laser centered')
        self.move_laser(0, 0)

    def move_laser(self, x, y, command: int = COMMAND_MOVE) -> None:
        logger.debug(f'laser moved to {x, y}')
        if self.is_errored:
            return
        self._next_command_point = (Point(x, y), command)

    def controller_is_ready(self) -> bool:
        return self.is_stable_position and self.is_ready and self._next_command_point is None

    def _notify_error(self, message: str):
        if self._notifier:
            self._notifier.show_error(message)

    def _notify_warning(self, message: str):
        if self._notifier:
            self._notifier.show_warning(message)


class SerialStub(Serial):
    READY_INTERVAL = 3  # sec

    def __init__(self):
        self._ready_timer = time()
        self._errored = False

    def generate_error(self):
        self._errored = True

    @property
    def _is_ready(self):
        return time() - self._ready_timer >= SerialStub.READY_INTERVAL

    def readline(self, **kwargs):
        if self._errored:
            self._errored = False
            return 'error'
        if self._is_ready:
            return 'ready'
        return ''

    def write(self, data):
        self._ready_timer = time()
