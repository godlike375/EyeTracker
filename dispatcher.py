from tkinter import Tk

from utils import XY, Settings, Pipeline
from area_controller import AreaController
from selector import Selector
from frame_process import Processor, FrameStorage, Tracker

class Dispatcher:
    def __init__(self, root: Tk, frame_storage: FrameStorage):
        self.working_area_selected = False
        self.selector = Selector()
        self.tk_root = root
        self.frame_storage = frame_storage
        self.tracker = Tracker()
        self.area_controller = AreaController(resolution_xy=10000, min_xy=-5000, max_xy=5000)
        self.frame_pipeline = Pipeline(self.default_processing)
        self.bind_events()
        self.frame_loop()

    # the main processing function of every frame. Being called every call_every ms
    def frame_loop(self):
        frame = self.frame_storage.get_raw_frame()
        self.tracking_off()
        #image = self.frame_pipeline.run_pure(frame)
        image = self.default_processing(frame)
        self.frame_storage._processed_image = image # the only place where _processed_image may be changed by design
        self.tk_root.after(Settings.CALL_EVERY, self.frame_loop)

    # the function of transforming raw frame to image
    # that will be passed to the main form and shown in the label
    def default_processing(self, frame):
        return Processor.frame_to_image(frame)

    def tracking_off(self):
        pass

    def tracking_on(self):
        frame = self.frame_storage.get_raw_frame()
        rect = self.tracker.get_tracked_position(frame)
        left_top, rigt_bottom = XY(int(rect.left()), int(rect.top())),\
                                XY(int(rect.right()), int(rect.bottom()))
        center = AreaController.calc_center(left_top, rigt_bottom)
        if self.area_controller.point_intersected_borders(*center):
            raise ValueError('the tracked object has intersected the borders')

    def bind_events(self):
        self.tk_root.bind('<B1-Motion>', self.progress)
        self.tk_root.bind('<Button-1>', self.start)
        self.tk_root.bind('<ButtonRelease-1>', self.end)

    def unbind_events(self):
        self.tk_root.unbind('<B1-Motion>')
        self.tk_root.unbind('<Button-1>')
        self.tk_root.unbind('<ButtonRelease-1>')

    def start(self, event):
        #self.frame_pipeline.add_func(self.selector.draw_selected_rect)
        self.default_processing = self.selector.draw_selected_rect
        self.selector.start(event)

    def progress(self, event):
        self.selector.progress(event)

    def end(self, event):
        self.selector.end(event)
        self.on_selected()

    def on_selected(self):
        if not self.working_area_selected:
            self.working_area_selected = True
            self.area_controller.set_area(self.selector.left_top, self.selector.right_bottom)
            return
        self.unbind_events()
        frame = self.frame_storage.get_raw_frame()
        self.tracker.start_tracking(frame, self.selector.left_top, self.selector.right_bottom)
        self.default_processing = self.tracker.draw_tracked_rect
        self.tracking_off = self.tracking_on
