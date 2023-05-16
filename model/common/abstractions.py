from abc import ABC, abstractmethod

from model.common.coordinates import Point
from model.common.thread_helpers import threaded


class Cancellable(ABC):

    @abstractmethod
    def cancel(self):
        ...


class ProcessBased:

    def __init__(self):
        self._in_progress = False
        self._is_done = False

    @property
    def in_progress(self):
        return self._in_progress

    @property
    def is_done(self):
        return self._is_done

    def start(self):
        self._in_progress = True
        self._is_done = False

    def cancel(self):
        self._in_progress = False
        self._is_done = False

    def finish(self):
        self._is_done = True
        self._in_progress = False


class RectBased:

    @property
    def left_top(self) -> Point:
        ...

    @property
    def right_bottom(self) -> Point:
        ...

    @property
    def center(self) -> Point:
        return (self.left_top + self.right_bottom) // 2


class Drawable(ABC):

    @abstractmethod
    def draw_on_frame(self, frame):
        ...


class Initializable:

    def __init__(self, initialized: bool = None):
        if initialized is None:
            self.initialized = False
            return
        self.initialized = initialized

    def init_error(self):
        self.initialized = False

    def init_success(self):
        self.initialized = True


class Calibrator(ABC):

    @threaded
    @abstractmethod
    def calibrate(self):
        ...

    @abstractmethod
    def _on_calibrated(self):
        ...
