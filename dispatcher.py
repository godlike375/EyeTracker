from tkinter import Tk

from area_controller import AreaController
from frame_processing import Processor, Tracker, FramePipeline
from selector import Selector
from utils import XY, Settings, FrameStorage
from move_controller import MoveController

AREA = 'area'
OBJECT = 'object'

class EventDispatcher:
    def __init__(self, root: Tk, frame_storage: FrameStorage):
        self.frame_pipeline = FramePipeline()
        self.area_selector = Selector(AREA, self.frame_pipeline, self.on_selected)
        self.object_selector = Selector(OBJECT, self.frame_pipeline, self.on_selected)
        self.tk_root = root
        self.frame_storage = frame_storage
        self.tracker = Tracker()
        self.area_controller = AreaController(resolution_xy=10000, min_xy=-5000, max_xy=5000)
        self.laser_controller = MoveController('com8')
        self.frame_loop()

    # the main processing function of every frame. Being called every call_every ms
    def frame_loop(self):
        frame = self.frame_storage.get_raw_frame()
        self.tracking_off()
        processed = self.frame_pipeline.run_pure(frame)
        image = Processor.frame_to_image(processed)

        self.frame_storage._processed_image = image # the only place where _processed_image may be changed by design
        self.tk_root.after(Settings.CALL_EVERY, self.frame_loop)

    def tracking_off(self):
        pass

    def tracking_on(self):
        frame = self.frame_storage.get_raw_frame()
        # TODO: в трекер должна передаваться только выделенная область cropped_image = img[80:280, 150:330]
        # TODO: сейчас похоже передаётся с рамкой от фона и большего, чем необходимо размера
        self.tracker.get_tracked_position(frame)
        relative_coords = self.area_controller.calc_relative_coords(self.tracker.center)
        if self.laser_controller.can_send(1.5):
            self.laser_controller.moveXY(*relative_coords)
        Processor.CURRENT_COLOR = Processor.COLOR_WHITE \
            if not self.area_controller.rect_intersected_borders(self.tracker.left_top, self.tracker.right_bottom)\
            else Processor.COLOR_RED
        # TODO: возможно всё-таки не по центру, а по краям считать с фильтрацией шумов

    def move_laser(self):
        pass

    def bind_events(self, selector):
        self.tk_root.bind('<B1-Motion>', selector.progress)
        self.tk_root.bind('<Button-1>', selector.start)
        self.tk_root.bind('<ButtonRelease-1>', selector.end)

    def unbind_events(self):
        self.tk_root.unbind('<B1-Motion>')
        self.tk_root.unbind('<Button-1>')
        self.tk_root.unbind('<ButtonRelease-1>')

    def reset_object_selection(self):
        self.bind_events(self.object_selector)
        pass

    def reset_area_selection(self):
        self.bind_events(self.area_selector)
        pass

    def on_selected(self, selector_name):
        if selector_name == AREA:
            self.working_area_selected = True
            self.area_controller.set_area(self.area_selector.left_top, self.area_selector.right_bottom)
            self.unbind_events()
            return
        
        frame = self.frame_storage.get_raw_frame()
        self.tracker.start_tracking(frame, self.object_selector.left_top, self.object_selector.right_bottom)
        # removing the pipeline of the object selector because it's not needed anymore
        self.frame_pipeline.pop_front()
        self.frame_pipeline.append_front(self.tracker.draw_tracked_rect)
        self.tracking_off = self.tracking_on
        self.unbind_events()
