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

        return elapsed_time >= self.count_every


class FPSLimiter:
    def __init__(self, fps_limit: int = 60):
        self.start_time = time.time()
        self.limit_time = 1 / fps_limit

    def able_to_execute(self):
        current_time = time.time()
        elapsed_time = current_time - self.start_time
        if elapsed_time >= self.limit_time:
            self.start_time = current_time
            return True
        return False

    def throttle(self):
        current_time = time.time()
        elapsed_time = current_time - self.start_time
        if elapsed_time < self.limit_time:
            throttle_time = self.limit_time - elapsed_time
            time.sleep(throttle_time)


FPS_50 = 1 / 50
FPS_120 = 1 / 120
MSEC_IN_SEC = 1000
