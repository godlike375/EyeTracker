from tkinter import Tk, messagebox

import cv2
from retry import retry

from model.area_controller import AreaController
from model.frame_processing import Processor, Tracker, FramePipeline
from model.move_controller import MoveController
from model.selector import Selector
from common.utils import Singleton, ThreadLoopable
from model.settings import Settings
from common.utils import Point


class FrameStorage(metaclass=Singleton):
    FRAME_INTERVAL = 1 / Settings.FPS
    def __init__(self):
        self._raw_frame = None
        self._processed_image = None

    @retry(RuntimeError, tries=100, delay=0.1, backoff=1)
    def get_image(self):
        if self._processed_image is None:
            raise RuntimeError('processed image was not initialized before being got')
        return self._processed_image

    @retry(RuntimeError, tries=100, delay=0.1, backoff=1)
    def get_raw_frame(self):
        if self._raw_frame is None:
            raise RuntimeError('raw frame was not initialized before being got')
        return self._raw_frame


class EventDispatcher(ThreadLoopable):
    def __init__(self, root: Tk, frame_storage: FrameStorage):

        self.root = root
        self.frame_pipeline = FramePipeline()
        self.area_selector = Selector('area', self.frame_pipeline, self.on_selected)
        self.object_selector = Selector('object', self.frame_pipeline, self.on_selected)
        self.frame_storage = frame_storage
        self.tracker = Tracker()
        self.area_controller = AreaController(min_xy=-Settings.MAX_RANGE,
                                              max_xy=Settings.MAX_RANGE)
        self.laser_controller = MoveController('com8')
        super().__init__(self.frame_processing, FrameStorage.FRAME_INTERVAL)

    # the main processing function of every frame. Being called every call_every ms
    def frame_processing(self):
        frame = self.frame_storage.get_raw_frame()
        self.tracking_off()
        processed = self.frame_pipeline.run_pure(frame)
        image = Processor.frame_to_image(processed)

        self.frame_storage._processed_image = image  # the only place where _processed_image may be changed by design

    def tracking_off(self):
        pass

    def tracking_on(self):
        frame = self.frame_storage.get_raw_frame()
        # TODO: в трекер должна передаваться только выделенная область cropped_image = img[80:280, 150:330]
        # TODO: сейчас похоже передаётся с рамкой от фона и большего, чем необходимо размера
        center = self.tracker.get_tracked_position(frame)
        relative_coords = self.area_controller.calc_relative_coords(center)
        intersected = self.area_controller.rect_intersected_borders(self.tracker.left_top, self.tracker.right_bottom)
        if not intersected:
            self.laser_controller.set_new_position(relative_coords.to_int())
        Processor.CURRENT_COLOR = Processor.COLOR_WHITE if not intersected else Processor.COLOR_RED

    def calibrate_laser(self):
        self.laser_controller._move_laser(Point(0, 0), command=2)

    def center_laser(self):
        self.laser_controller._move_laser(Point(0, 0))

    def bind_events(self, selector: Selector):
        self.root.bind('<B1-Motion>', selector.progress)
        self.root.bind('<Button-1>', selector.start)
        self.root.bind('<ButtonRelease-1>', selector.end)

    def unbind_events(self):
        self.root.unbind('<B1-Motion>')
        self.root.unbind('<Button-1>')
        self.root.unbind('<ButtonRelease-1>')

    def reset_object_selection(self):
        self.frame_pipeline.safe_remove(self.tracker.draw_tracked_rect)
        self.bind_events(self.object_selector)

    def reset_area_selection(self):
        self.frame_pipeline.safe_remove(self.area_selector.draw_selected_rect)
        self.bind_events(self.area_selector)

    def on_selected(self, selector_name: str):
        # TODO: видимо разнести на 2 метода, чтобы не делать костыльных условий
        if selector_name == 'area':
            if self.area_selector.left_top == self.area_selector.right_bottom:
                messagebox.showerror(message='Область не может быть пустой')
                return
            self.area_controller.set_area(self.area_selector.left_top, self.area_selector.right_bottom)
            self.unbind_events()
            return

        frame = self.frame_storage.get_raw_frame()
        self.tracker.start_tracking(frame, self.object_selector.left_top, self.object_selector.right_bottom)
        # removing the pipeline of the object selector because it's not needed anymore
        self.frame_pipeline.safe_remove(self.object_selector.draw_selected_rect)
        self.frame_pipeline.append(self.tracker.draw_tracked_rect)
        self.tracking_off = self.tracking_on
        self.unbind_events()


class Extractor(ThreadLoopable):

    def __init__(self, source: int, frame_storage: FrameStorage):
        self.set_source(source)
        super().__init__(self.extract_frame, FrameStorage.FRAME_INTERVAL)
        self.frame_storage = frame_storage

    def set_source(self, source):
        self.camera = cv2.VideoCapture(source)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, Settings.CAMERA_MAX_RESOLUTION)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, Settings.CAMERA_MAX_RESOLUTION)
        self.camera.set(cv2.CAP_PROP_FPS, Settings.FPS)
        if self.camera.isOpened():
            return
        print('Камера не найдена')
        exit()

    def extract_frame(self):
        _, frame = self.camera.read()
        self.frame_storage._raw_frame = frame  # the only one who can do it
        return frame