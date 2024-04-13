import time


class FPSCounter:
    def __init__(self, count_every_seconds: float = 1.0):
        self.start_time = time.time()
        self.frames = 0
        self.count_every = count_every_seconds

    def calculate(self):
        current_time = time.time()
        elapsed_time = current_time - self.start_time

        if elapsed_time >= self.count_every:
            fps = self.frames / elapsed_time
            self.frames = 0
            self.start_time = current_time
            return fps
        else:
            return 0

    def count_frame(self):
        self.frames += 1

    def able_to_calculate(self):
        current_time = time.time()
        elapsed_time = current_time - self.start_time

        if elapsed_time >= 1.0:
            return True
        else:
            return False
