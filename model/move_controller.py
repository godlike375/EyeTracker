from time import time
import logging

from serial import Serial

from common.utils import Point, LOGGER_NAME
from model.settings import Settings

STABLE_POSITION_DURATION = 0.67
READY = 'ready'

logger = logging.getLogger(LOGGER_NAME)

class MoveController:
    def __init__(self, port=None, baund_rate=None):
        # TODO: к настройкам должно обращаться что-то внещнее в идеале и передавать эти параметры сюда
        port = port or f'com{Settings.SERIAL_PORT}'
        baund_rate = baund_rate or Settings.SERIAL_BAUND_RATE
        self.serial = Serial(port, baund_rate, timeout=Settings.SERIAL_TIMEOUT)
        self.timer = time()
        self.current_position = Point(0, 0)
        self._ready = True
        self.timer = time()

    def _can_send(self, interval: float = STABLE_POSITION_DURATION):
        if time() - self.timer > interval:
            return True
        return False

    def _is_ready(self):
        if not self._ready:
            line = self.serial.readline()
            if READY in str(line):
                self._ready = True
        return self._ready

    def _move_laser(self, position: Point, command=1):
        position.to_int()
        message = (f'{position.x};{position.y};{command}\n').encode('ascii', 'ignore')
        logger.debug(f'moving laser to {position.x, position.y}, command={command}')
        self.serial.write(message)
        self.timer = time()
        self._ready = False

    def set_new_position(self, position: Point):
        if position == self.current_position:
            return
        if not self._can_send and not self._is_ready():
            return
        self.timer = time()
        self.current_position = position
        self._move_laser(position)
