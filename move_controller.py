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

    @staticmethod
    def can_send(interval=2):
        global timing
        if time() - timing > interval:
            return True
        return False

    @staticmethod
    def reset():
        global timing
        timing = time()

    def moveXY(self, x,y, command=1):
        # TODO: в конце сеанса отправлять 0;0 для сброса позиционирования
        message = (f'{int(x)};{int(y)};{command}').encode('ascii', 'ignore')
        self.serial.write(message)
        self.serial.readable()
        print(self.serial.readline())
        self.current_xy.x, self.current_xy.y = x, y
        print(message)
        #time.sleep(1)