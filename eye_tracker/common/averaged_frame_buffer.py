import numpy as np


class AveragedFrameBuffer:
    def __init__(self, frame_count):
        self.frame_count = frame_count
        self.frames = []
        self.current_index = 0
        self.is_full = False

    def add_frame(self, frame):
        # Проверка размера кадра (чтобы избежать проблем с размером)
        if not self.frames:
            self.frames.append(frame)
        else:
            if frame.shape != self.frames[0].shape:
                raise ValueError("Frame shape must match the shape of existing frames")

        # Добавление кадра в буфер
        if self.is_full:
            self.frames[self.current_index] = frame
        else:
            self.frames.append(frame)
            if len(self.frames) == self.frame_count:
                self.is_full = True

        self.current_index = (self.current_index + 1) % self.frame_count

    def get_average_frame(self):
        if not self.frames:
            raise ValueError("No frames to average")

        average_frame = np.mean(self.frames, axis=0).astype(np.uint8)
        return average_frame