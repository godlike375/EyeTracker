from abc import ABC, abstractmethod

class ProcessBased(ABC):

    def __init__(self):
        self.in_progress = False

    def start(self):
        self.in_progress = True

    def stop(self):
        self.in_progress = False


class RectBased(ABC):

    @property
    def left_top(self):
        pass

    @property
    def right_bottom(self):
        pass


class Drawable(ABC):

    @abstractmethod
    def draw_on_frame(self, frame):
        raise NotImplementedError


class Initializable(ABC):

    def __init__(self, initialized: bool = None):
        if initialized is None:
            self.initialized = False
            return
        self.initialized = initialized

    def init_error(self):
        self.initialized = False

    def init_success(self):
        self.initialized = True