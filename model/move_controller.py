from time import time

from serial import Serial, SerialException
from serial.tools import list_ports

from common.coordinates import Point
from common.settings import Settings
from view.view_model import ViewModel
from common.logger import logger

READY = 'ready'


class MoveController:

    def __init__(self, manual_port=None, baund_rate=None, serial_off=False):
        # TODO: к настройкам должно обращаться что-то внещнее в идеале и передавать эти параметры сюда
        # TODO: MUST HAVE сделать автоопределение порта с помощью перебора или поиска по имени устройства
        manual_port = manual_port or f'COM{Settings.SERIAL_PORT}'
        baund_rate = baund_rate or Settings.SERIAL_BAUND_RATE
        self._timer = time()
        self._current_position = Point(0, 0)
        self._ready = True
        self._timer = time()
        self._serial = MockSerial()
        if serial_off:
            ViewModel.show_message('Последовательный порт используется в режиме отладки', 'Предупреждение')
            return

        try:
            self._serial = Serial(manual_port, baund_rate, timeout=Settings.SERIAL_TIMEOUT)
        except SerialException:
            logger.exception('Manual com port was not found. Attempting to use auto-detection')

        auto_detected = manual_port
        com_ports = list_ports.comports()
        for p in com_ports:
            if 'usb-serial ch340' in p.description.lower():
                auto_detected = p.device

        try:
            self._serial = Serial(auto_detected, baund_rate, timeout=Settings.SERIAL_TIMEOUT)
        except SerialException as e:
            logger.exception(str(e))
            ViewModel.show_message(f'Не удалось открыть заданный настройками последовательный порт '
                                   f'{manual_port}, а так же не удалось определить подходящий порт автоматически. '
                                   f'Программа продолжит работать без контроллера лазера.', 'Предупреждение')




    @property
    def _can_send(self):
        if time() - self._timer > Settings.STABLE_POSITION_DURATION:
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
