import logging

from common.utils import Point, LOGGER_NAME
from common.utils import Singleton, ThreadLoopable
from model.area_controller import AreaController
from model.extractor import Extractor
from model.frame_processing import Processor, Tracker, FramePipeline
from model.move_controller import MoveController
from model.selector import Selector
from model.settings import Settings
from view.view_model import ViewModel

logger = logging.getLogger(LOGGER_NAME)

FRAME_INTERVAL = 1 / Settings.FPS


class Model(ThreadLoopable, metaclass=Singleton):

    def __init__(self, view_model: ViewModel, run_immediately: bool = True):
        self._view_model = view_model
        self._extractor = Extractor(Settings.CAMERA_ID)
        self._pipeline = FramePipeline()
        self._tracker = Tracker()
        self._area_controller = AreaController(min_xy=-Settings.MAX_RANGE,
                                               max_xy=Settings.MAX_RANGE)
        self._laser_controller = MoveController()
        self._selectors = {
            'area': Selector('area', self.on_area_selected),
            'object': Selector('object', self.on_object_selected)
                            }
        self._current_frame = None
        self._tracking = self._tracking_off
        super().__init__(self._processing_loop, FRAME_INTERVAL, run_immediately)

    def get_selector(self, name):
        selector = self._selectors.get(name)
        if selector is None:
            raise IndexError(f'there is no {name} selector in selectors list')
        return selector

    def _processing_loop(self):
        frame = self._current_frame = self._extractor.extract_frame()
        processed_image = self._frame_processing(frame)
        self._view_model.on_image_ready(processed_image)

    def _frame_processing(self, frame):
        self._tracking(frame)
        processed = self._pipeline.run_pure(frame)
        return Processor.frame_to_image(processed)

    def _tracking(self):
        pass

    def _tracking_off(self, frame):
        pass

    def _tracking_on(self, frame):
        # TODO: в трекер должна передаваться только выделенная область cropped_image = img[80:280, 150:330]
        # TODO: сейчас похоже передаётся с рамкой от фона и большего, чем необходимо размера
        center = self._tracker.get_tracked_position(frame)
        relative_coords = self._area_controller.calc_relative_coords(center)
        intersected = self._area_controller.rect_intersected_borders(self._tracker.left_top, self._tracker.right_bottom)
        if not intersected:
            self._laser_controller.set_new_position(relative_coords.to_int())
        Processor.CURRENT_COLOR = Processor.COLOR_WHITE if not intersected else Processor.COLOR_RED

    def calibrate_laser(self):
        self._laser_controller._move_laser(Point(0, 0), command=2)

    def center_laser(self):
        self._laser_controller._move_laser(Point(0, 0))

    def remove_processor(self, name):
        self._pipeline.safe_remove(name)

    def add_selector_pipeline(self, selector: Selector):
        self._pipeline.append(selector.draw_selected_rect)

    def on_area_selected(self):
        area = self.get_selector('area')
        if area.is_empty():
            self._view_model.show_message('Область не может быть пустой', 'Ошибка')
        self._area_controller.set_area(area.left_top, area.right_bottom)

    def on_object_selected(self):
        object = self.get_selector('object')
        # TODO: для улучшения производительности стоит в трекер подавать только выделенную область, а не весь кадр
        self._tracker.start_tracking(self._current_frame, object.left_top,
                                     object.right_bottom)
        # removing the pipeline of the object selector because it's not needed anymore
        self._pipeline.safe_remove(object.draw_selected_rect)
        self._pipeline.append(self._tracker.draw_tracked_rect)
        self._tracking = self._tracking_on
