from serial import Serial

from common.utils import Point
from time import time
from model.settings import Settings
from common.utils import thread_loop_runner

MIN_SEND_INTERVAL = 0.75

class MoveController:

    def __init__(self, port = None, baund_rate = None):
        # TODO: к настройкам должно обращаться что-то внещнее в идеале и передавать эти параметры сюда
        port = port or f'com{Settings.SERIAL_PORT}'
        baund_rate = baund_rate or Settings.SERIAL_BAUND_RATE
        self.serial = Serial(port, baund_rate, timeout=Settings.SERIAL_TIMEOUT)
        self.timer = time()
        self.current_position = Point(0, 0)
        self._ready = True
        #sleep(2) # выдержка для инициализации serial port
        self.timer = time()
        self.queued_position = None
        self.queued_thread = None

    def can_send(self, interval=MIN_SEND_INTERVAL):
        if time() - self.timer > interval:
            return True
        return False

    def is_ready(self):
        if not self._ready:
            line = self.serial.readline()
            if 'ready' in str(line):
                self._ready = True
        return self._ready

    def _move_laser(self, position: Point, command=1):
        # TODO: в конце сеанса отправлять 0;0 для сброса позиционирования
        message = (f'{int(position.x)};{int(position.y)};{command}').encode('ascii', 'ignore')
        self.serial.write(message)
        print(message)
        self.timer = time()
        self._ready = False

    def set_new_position(self, position: Point):
        if position == self.current_position:
            return
        self.timer = time()
        self.current_position = position
        if self.can_send() and self.is_ready():
            self._move_laser(position)
            if self.queued_thread is not None:
                self.queued_thread.stop()
        else:
            self.queued_position = position
            if self.queued_thread is None:
                self.queued_thread = thread_loop_runner(self._wait_for_queued, 0.05)
                self.queued_thread.start()

    def _wait_for_queued(self):
        if self.can_send() and self.is_ready():
            self._move_laser(self.queued_position)
            self.queued_thread.stop()
            self.queued_thread = None