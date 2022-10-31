from serial import Serial

from common.utils import Point
from time import time, sleep
from model.settings import Settings

MIN_SEND_INTERVAL = 0.7

class MoveController:

    def __init__(self, port = None, baund_rate = None):
        # TODO: к настройкам должно обращаться что-то внещнее в идеале и передавать эти параметры сюда
        port = port or f'com{Settings.SERIAL_PORT}'
        baund_rate = baund_rate or Settings.SERIAL_BAUND_RATE
        self.serial = Serial(port, baund_rate, timeout=Settings.SERIAL_TIMEOUT)
        self.timer = time()
        self.current_position = Point(0, 0)
        self._ready = False
        sleep(2) # выдержка для инициализации serial port
        self.timer = time()

    def can_send(self, interval=2):
        if time() - self.timer > interval:
            return True
        return False

    def is_ready(self):
        if not self._ready:
            line = self.serial.readline()
            if 'ready' in str(line):
                self._ready = True
        return self._ready

    def move_laser(self, position: Point, command=1):
        # TODO: в конце сеанса отправлять 0;0 для сброса позиционирования
        message = (f'{int(position.x)};{int(position.y)};{command}').encode('ascii', 'ignore')
        self.serial.write(message)
        print(message)
        self.timer = time()

    def set_new_position(self, position: Point):
        if position != self.current_position:
            self.timer = time()
            self.current_position = position
        if self.can_send(MIN_SEND_INTERVAL) and self.is_ready():
            self.move_laser(position)
            self._ready = False
