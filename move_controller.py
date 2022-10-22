from serial import Serial

from utils import XY, Settings
from time import time, sleep


class MoveController:

    def __init__(self, port = None, bandwidth = None):
        port = port or Settings.PORT
        bandwidth = bandwidth or Settings.BANDWIDTH
        self.serial = Serial(port, bandwidth, timeout=Settings.TIMEOUT)
        self.timer = time()
        self.current_xy = XY(0,0)
        sleep(2)
        self.moveXY(0, 0, 2)
        self.timing = time()

    def can_send(self, interval=2):
        if time() - self.timing > interval:
            return True
        return False

    def moveXY(self, x,y, command=1):
        # TODO: в конце сеанса отправлять 0;0 для сброса позиционирования
        message = (f'{int(x)};{int(y)};{command}').encode('ascii', 'ignore')
        self.serial.write(message)
        self.serial.readable()
        print(self.serial.readline())
        self.current_xy.x, self.current_xy.y = x, y
        print(message)
        self.timing = time()
        #time.sleep(1)