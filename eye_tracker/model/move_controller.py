from time import time

from serial import Serial, SerialException
from serial.tools import list_ports

from eye_tracker.common.abstractions import Initializable
from eye_tracker.common.coordinates import Point
from eye_tracker.common.logger import logger
from eye_tracker.common.settings import settings, CALIBRATE_LASER_COMMAND, MAX_LASER_RANGE
from eye_tracker.common.thread_helpers import ThreadLoopable, MutableValue
from eye_tracker.view import view_output

READY = 'ready'
ERRORED = 'error'
LASER_DEVICE_NAME = 'usb-serial ch340'
COMMAND_MOVE = 1
DEFAULT_BAUD_RATE = 115200
SERIAL_TIMEOUT = 0.1


class MoveController(Initializable, ThreadLoopable):

    def __init__(self, on_laser_error, manual_port=None, baud_rate=None, debug_on=False, run_immediately=True):
        Initializable.__init__(self, initialized=True)

        manual_port = manual_port or f'COM{settings.SERIAL_PORT}'
        baud_rate = baud_rate or DEFAULT_BAUD_RATE
        self._stable_position_timer = 0
        self._current_position = Point(0, 0)
        self._ready = False
        self._errored = False
        self._current_line = ''
        self._serial = SerialStub()
        self._on_laser_error = on_laser_error
        self._pool_interval = MutableValue(1 / int(settings.FPS_PROCESSED * 0.5))
        self._next_command_point = None

        left_top = Point(-MAX_LASER_RANGE, -MAX_LASER_RANGE)
        right_top = Point(MAX_LASER_RANGE, -MAX_LASER_RANGE)
        right_bottom = Point(MAX_LASER_RANGE, MAX_LASER_RANGE)
        left_bottom = Point(-MAX_LASER_RANGE, MAX_LASER_RANGE)
        self.laser_borders = [left_top, right_top, right_bottom, left_bottom]

        if debug_on:
            view_output.show_warning('Последовательный порт используется в режиме отладки')
            ThreadLoopable.__init__(self, self._processing_loop, self._pool_interval, run_immediately=run_immediately)
            return

        try:
            ports_names = {p.name: p.description.lower() for p in list_ports.comports()}
            ports_descriptions = {p.description.lower(): p.name for p in list_ports.comports()}
            if manual_port not in ports_names or ports_names[manual_port] != LASER_DEVICE_NAME:
                predicate = [(LASER_DEVICE_NAME in description) for description in ports_descriptions]
                if not any(predicate):
                    view_output.show_error(
                        f'Не удалось открыть заданный настройкой SERIAL_PORT последовательный порт'
                        f' {manual_port}, а так же не удалось определить подходящий порт автоматически.'
                        f' Программа продолжит работать без контроллера лазера.')
                    self.init_error()
                    ThreadLoopable.__init__(self, self._processing_loop, self._pool_interval,
                                            run_immediately=run_immediately)
                    return

                for description in ports_descriptions:
                    if LASER_DEVICE_NAME in description:
                        manual_port = ports_descriptions[description]
            serial = Serial(manual_port, baud_rate, timeout=SERIAL_TIMEOUT)
        except SerialException:
            logger.exception('Cannot open the proper serial port')
        else:
            self._serial = serial

        ThreadLoopable.__init__(self, self._processing_loop, self._pool_interval, run_immediately=run_immediately)

    def _processing_loop(self):
        serial_data = self._serial.readline()
        new_errored = self._errored or ERRORED in str(serial_data)

        if new_errored and self._errored != new_errored:
            view_output.show_error('Контроллер лазера внезапно дошёл до предельных координат. \n'
                                   'Необходимо откалибровать контроллер лазера повторно. '
                                   'До этого момента слежение за объектом невозможно')
            self._errored = new_errored
            self._on_laser_error()
            return

        if self.is_errored:
            return

        self._ready = self._ready or READY in str(serial_data)

        if not self.is_ready or self._next_command_point is None:
            return

        if self._next_command_point[1] == CALIBRATE_LASER_COMMAND or \
                self.is_stable_position:
            self._move_laser(*self._next_command_point)
            self._stable_position_timer = time()
            self._ready = False
            self._next_command_point = None

    @property
    def is_stable_position(self):
        if time() - self._stable_position_timer > settings.STABLE_POSITION_DURATION:
            return True
        return False

    @property
    def is_ready(self):
        return self._ready

    @property
    def is_errored(self):
        return self._errored

    def _move_laser(self, position: Point, command=COMMAND_MOVE):
        message = (f'{position.x};{position.y};{command}\n').encode('ascii', 'ignore')
        self._serial.write(message)

    def set_new_position(self, position: Point):
        if position == self._current_position:
            return

        if self.is_errored:
            return

        if not self.is_stable_position:
            return

        if abs(position.x) > MAX_LASER_RANGE or \
                abs(position.y) > MAX_LASER_RANGE:
            logger.debug('can\'t set out of laser range position')
            return

        self._stable_position_timer = time()
        self._current_position = position
        self._next_command_point = (position, COMMAND_MOVE)

    def calibrate_laser(self):
        logger.debug('laser calibrated')
        self._errored = False
        self.move_laser(0, 0, command=CALIBRATE_LASER_COMMAND)

    def center_laser(self):
        logger.debug('laser centered')
        self.move_laser(0, 0)

    def move_laser(self, x, y, command=COMMAND_MOVE):
        logger.debug(f'laser moved to {x, y}')

        if self.is_errored:
            return

        self._next_command_point = (Point(x, y), command)

    def controller_is_ready(self):
        return self.is_stable_position and self.is_ready


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
