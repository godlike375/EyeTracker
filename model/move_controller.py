from time import time

from serial import Serial, SerialException
from serial.tools import list_ports

from common.coordinates import Point
from common.logger import logger
from common.settings import settings
from common.abstractions import Initializable
from view import view_output

READY = 'ready'
ERRORED = 'error'
LASER_DEVICE_NAME = 'usb-serial ch340'


class MoveController(Initializable):

    def __init__(self, manual_port=None, baud_rate=None, serial_off=False):
        super().__init__(initialized=True)
        # TODO: к настройкам должно обращаться что-то внещнее в идеале и передавать эти параметры сюда
        manual_port = manual_port or f'COM{settings.SERIAL_PORT}'
        baud_rate = baud_rate or settings.SERIAL_BAUD_RATE
        self._timer = time()
        self._current_position = Point(0, 0)
        self._ready = True
        self._errored = False
        self._current_line = ''
        self._timer = time()
        self._serial = SerialStub()
        if serial_off:
            view_output.show_message('Последовательный порт используется в режиме отладки', 'Предупреждение')
            return

        try:
            self._serial = Serial(manual_port, baud_rate, timeout=settings.SERIAL_TIMEOUT)
        except SerialException:
            logger.exception('Manual com port was not found. Attempting to use auto-detection')

        auto_detected = manual_port
        com_ports = list_ports.comports()
        for p in com_ports:
            if LASER_DEVICE_NAME in p.description.lower():
                auto_detected = p.device

        try:
            self._serial = Serial(auto_detected, baud_rate, timeout=settings.SERIAL_TIMEOUT)
        except SerialException as e:
            self.init_error()
            logger.exception(str(e))
            view_output.show_warning(f'Не удалось открыть заданный настройкой SERIAL_PORT последовательный порт '
                                     f'{manual_port}, а так же не удалось определить подходящий порт автоматически. '
                                     f'Программа продолжит работать без контроллера лазера.')

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

    def _move_laser(self, position: Point, command=1):
        message = (f'{position.x};{position.y};{command}\n').encode('ascii', 'ignore')
        # Конвертация в систему координат контроллера лазера
        # {position.y};{-position.x}
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
    READY_INTERVAL = 0.005  # sec

    def __init__(self):
        self._ready_timer = time()

    @property
    def _is_ready(self):
        ready = time() - self._ready_timer >= SerialStub.READY_INTERVAL
        if ready:
            self._ready_timer = time()
        return ready

    def readline(self, **kwargs):
        if self._is_ready:
            return 'ready'
        return ''

    def write(self, data):
        pass
