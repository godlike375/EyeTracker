import serial
from time import time, sleep
pixel_per_mm = 8.7
steps_per_mm = 500
X,Y = 0,0 #текущее положение луча

ser = None
timing = time()
def init(port='com7', bandwidth=19200):
    global ser
    ser = serial.Serial(port, bandwidth)
    sleep(2)

def canSend(interval=2):
    global timing
    if time() - timing > interval:
        return True
    return False

def reset():
    global timing
    timing = time()

def moveXY(x,y):
    global X, Y
    ser.write((str(x) + ';' + str(y)).encode('ascii', 'ignore'))
    X, Y = x,y
    #time.sleep(1)

def moveY(y):
    global Y
    if canSend():
        ser.write((str(X) + ';' + str(y)).encode('ascii', 'ignore'))
        Y = y
        reset()
    #time.sleep(1)

def moveX(x):
    if canSend():
        global X
        ser.write((str(x) + ';' + str(Y)).encode('ascii', 'ignore'))
        X = x
        reset()
    #time.sleep(1)