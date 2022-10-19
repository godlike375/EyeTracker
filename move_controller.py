import serial
from time import time, sleep


class MoveController:
    pixel_per_mm = 8.7
    steps_per_mm = 500
    X,Y = 0,0 #текущее положение луча

    ser = None
    timing = time()

    @staticmethod
    def init(port = 'com7', bandwidth = 19200):
        global ser
        ser = serial.Serial(port, bandwidth)
        sleep(2)

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

    @staticmethod
    def moveXY(x,y):
        global X, Y
        ser.write((f'{x};{y};1').encode('ascii', 'ignore'))
        X, Y = x,y
        print(x,y)
        #time.sleep(1)