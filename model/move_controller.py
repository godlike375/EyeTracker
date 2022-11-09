import logging
from time import time

from serial import Serial

from common.coordinates import Point
from common.settings import Settings
from common.thread_helpers import LOGGER_NAME

READY = 'ready'

logger = logging.getLogger(LOGGER_NAME)


class MoveController:
    STABLE_POSITION_DURATION = 0.67

    def __init__(self, port=None, baund_rate=None, serial_off=False):
        # TODO: к настройкам должно обращаться что-то внещнее в идеале и передавать эти параметры сюда
        port = port or f'com{Settings.SERIAL_PORT}'
        baund_rate = baund_rate or Settings.SERIAL_BAUND_RATE
        self._timer = time()
        self._current_position = Point(0, 0)
        self._ready = True
        self._timer = time()
        self._serial = Serial(port, baund_rate, timeout=Settings.SERIAL_TIMEOUT) \
            if serial_off else MockSerial()

    @property
    def _can_send(self):
        if time() - self._timer > MoveController.STABLE_POSITION_DURATION:
            return True
        return False

    @property
    def _is_ready(self):
        if not self._ready:
            line = self._serial.readline()
            if READY in str(line):
                self._ready = True
        return self._ready

    def _move_laser(self, position: Point, command=1):
        message = (f'{position.x};{position.y};{command}\n').encode('ascii', 'ignore')
        self._serial.write(message)
        self._timer = time()
        self._ready = False

    def set_new_position(self, position: Point):
        if position == self._current_position:
            return
        if not self._can_send and not self._is_ready:
            return
        self._timer = time()
        self._current_position = position
        self._move_laser(position)


class MockSerial(Serial):
    READY_INTERVAL = 0.005  # sec

    def __init__(self):
        self._ready_timer = time()

    @property
    def _is_ready(self):
        ready = time() - self._ready_timer >= MockSerial.READY_INTERVAL
        if ready:
            self._ready_timer = time()
        return ready

    def readline(self, **kwargs):
        if self._is_ready:
            return 'ready'
        return ''

    def write(self, data):
        pass
