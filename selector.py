from frame_processing import Processor, FramePipeline
from utils import XY


class Selector:
    def __init__(self, pipeline: FramePipeline, callback):
        self.pipeline = pipeline
        self.left_top = XY(0, 0)
        self.right_bottom = XY(0, 0)
        self.callback = callback

    def start(self, event):
        self.pipeline.append_front(self.draw_selected_rect)
        self.left_top.x, self.left_top.y = event.x, event.y

    def progress(self, event):
        self.right_bottom.x, self.right_bottom.y = event.x, event.y

    def end(self, event):
        self.right_bottom.x, self.right_bottom.y = event.x, event.y
        self.left_top.x, self.right_bottom.x = Selector.check_swap_coords(self.left_top.x, self.right_bottom.x)
        self.left_top.y, self.right_bottom.y = Selector.check_swap_coords(self.left_top.y, self.right_bottom.y)
        self.callback()

    def draw_selected_rect(self, frame):
        rect_frame = Processor.draw_rectangle(frame, tuple(self.left_top), tuple(self.right_bottom))
        return rect_frame

    @staticmethod
    def check_swap_coords(x1, x2):
        return (x2, x1) if x2 <= x1 else (x1, x2)
