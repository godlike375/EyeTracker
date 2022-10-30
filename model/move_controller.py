from serial import Serial

from common.utils import Point
from time import time, sleep
from model.settings import Settings


class MoveController:

    def __init__(self, port = None, baund_rate = None):
        # TODO: к настройкам должно обращаться что-то внещнее в идеале и передавать эти параметры сюда
        port = port or f'com{Settings.SERIAL_PORT}'
        baund_rate = baund_rate or Settings.SERIAL_BAUND_RATE
        self.serial = Serial(port, baund_rate, timeout=Settings.SERIAL_TIMEOUT)
        self.timer = time()
        self.current_xy = Point(0, 0)
        self._ready = False
        sleep(2) # выдержка для инициализации serial port
        self.timing = time()

    def can_send(self, interval=2):
        if time() - self.timing > interval:
            return True
        return False

    def is_ready(self):
        if not self._ready:
            line = self.serial.readline()
            if 'ready' in str(line):
                self._ready = True
                print('ready')
        return self._ready


    def moveXY(self, x,y, command=1):
        # TODO: в конце сеанса отправлять 0;0 для сброса позиционирования
        message = (f'{int(x)};{int(y)};{command}').encode('ascii', 'ignore')
        self.serial.write(message)
        self.serial.readable()
        print(self.serial.readline())
        self.current_xy.x, self.current_xy.y = x, y
        print(message)
        self.timing = time()
        self._ready = False
        #time.sleep(1)