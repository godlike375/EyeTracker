from time import time

from serial import Serial, SerialException
from serial.tools import list_ports

from common.abstractions import Initializable
from common.coordinates import Point
from common.logger import logger
from common.settings import settings
from view import view_output

READY = 'ready'
ERRORED = 'error'
LASER_DEVICE_NAME = 'usb-serial ch340'


class MoveController(Initializable):

    def __init__(self, manual_port=None, baud_rate=None, debug_on=False):
        super().__init__(initialized=True)
        manual_port = manual_port or f'COM{settings.SERIAL_PORT}'
        baud_rate = baud_rate or settings.SERIAL_BAUD_RATE
        self._timer = time()
        self._current_position = Point(0, 0)
        self._ready = True
        self._errored = False
        self._current_line = ''
        self._timer = time()
        self._serial = SerialStub()
        if debug_on:
            view_output.show_warning('Последовательный порт используется в режиме отладки')
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
                    return
                for description in ports_descriptions:
                    if LASER_DEVICE_NAME in description:
                        manual_port = ports_descriptions[description]
            serial = Serial(manual_port, baud_rate, timeout=settings.SERIAL_TIMEOUT)
        except SerialException:
            logger.exception('Cannot open the proper serial port')
        else:
            self._serial = serial

    @property
    def can_send(self):
        if time() - self._timer > settings.STABLE_POSITION_DURATION:
            return True
        return False

    @property
    def is_ready(self):
        if not self._ready:
            if READY in str(self._current_line):
                self._ready = True
        return self._ready

    @property
    def is_errored(self):
        if not self._errored:
            if ERRORED in str(self._current_line):
                self._errored = True
        return self._errored

    def read_line(self):
        self._current_line = self._serial.readline()
        self.is_ready
        self.is_errored

    def _move_laser(self, position: Point, command=1):
        message = (f'{position.x};{position.y};{command}\n').encode('ascii', 'ignore')
        self._serial.write(message)
        self._timer = time()
        self._ready = False

    def set_new_position(self, position: Point):
        if abs(position.x) > settings.MAX_LASER_RANGE_PLUS_MINUS or \
                abs(position.y) > settings.MAX_LASER_RANGE_PLUS_MINUS:
            return
        if position == self._current_position:
            return
        self._timer = time()
        self._current_position = position
        self._move_laser(position)


class SerialStub(Serial):
    READY_INTERVAL = 3  # sec

    def __init__(self):
        self._ready_timer = time()

    @property
    def _is_ready(self):
        return time() - self._ready_timer >= SerialStub.READY_INTERVAL

    def readline(self, **kwargs):
        if self._is_ready:
            return 'ready'
        return ''

    def write(self, data):
        self._ready_timer = time()
