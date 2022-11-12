import _thread
import logging

from common.coordinates import Point
from common.settings import Settings, OBJECT, AREA
from common.thread_helpers import LOGGER_NAME, ThreadLoopable
from model.area_controller import AreaController
from model.extractor import Extractor
from model.frame_processing import Tracker
from model.move_controller import MoveController
from model.selector import Selector
from view.drawing import Processor
from view.view_model import ViewModel

logger = logging.getLogger(LOGGER_NAME)

FRAME_INTERVAL = 1 / Settings.FPS


class Model(ThreadLoopable):

    def __init__(self, view_model: ViewModel, run_immediately: bool = True, area: tuple = None):
        self._view_model = view_model
        self._extractor = Extractor(Settings.CAMERA_ID)
        self._tracker = Tracker()
        self._area_controller = AreaController(min_xy=-Settings.MAX_RANGE,
                                               max_xy=Settings.MAX_RANGE)
        self._laser_controller = MoveController(serial_off=True)
        self._selectors = dict()
        self._current_frame = None
        self._drawed_boxes = dict()  # {name: RectBased}

        if area is not None:
            self.load_selected_area(area)

        super().__init__(self._processing_loop, FRAME_INTERVAL, run_immediately)

    def load_selected_area(self, area):
        left_top, right_bottom = area
        area_selector = Selector(AREA, self.on_area_selected, left_top, right_bottom)
        area_selector._selected = True
        self._selectors[AREA] = area_selector
        self.start_drawing_selected(area_selector)
        self.on_area_selected()

    def get_or_create_selector(self, name):
        selector = self._selectors.get(name)
        if selector is None:
            logger.debug(f'creating new selector {name}')
            on_selected = self.on_object_selected if OBJECT in name else self.on_area_selected
            selector = Selector(name, on_selected)
            self._selectors[name] = selector
        return selector

    def _processing_loop(self):
        try:
            frame = self._current_frame = self._extractor.extract_frame()
            processed_image = self._frame_processing(frame)
            self._view_model.on_image_ready(processed_image)
        except Exception as e:
            ViewModel.show_message(title='Фатальная ошибка', message=f'{e}')
            logger.exception(e)
            _thread.interrupt_main()

    def _frame_processing(self, frame):
        if self._tracker.in_progress:
            self._tracking(frame)
        boxes = self._drawed_boxes.values()
        processed = Processor.draw_boxes(frame, boxes)
        return Processor.frame_to_image(processed)

    def _tracking(self, frame):
        if not self._tracker.in_progress:
            return
        area = self.get_or_create_selector(AREA)
        cropped_frame = Processor.crop_frame(frame, area.left_top, area.right_bottom)
        center = self._tracker.get_tracked_position(cropped_frame, area.left_top)
        self._move_to_relative_cords(center)

    def _move_to_relative_cords(self, center):
        relative_coords = self._area_controller.calc_relative_coords(center)
        out_of_area = self._area_controller.rect_intersected_borders(self._tracker.left_top, self._tracker.right_bottom)
        if not out_of_area:
            self._laser_controller.set_new_position(relative_coords.to_int())
        Processor.CURRENT_COLOR = Processor.COLOR_WHITE if not out_of_area else Processor.COLOR_RED

    def calibrate_laser(self):
        logger.debug('laser calibrated')
        self._laser_controller._move_laser(Point(0, 0), command=2)

    def center_laser(self):
        logger.debug('laser centered')
        self._laser_controller._move_laser(Point(0, 0))

    def stop_drawing_selected(self, name):
        if name in self._drawed_boxes:
            del self._drawed_boxes[name]

    def start_drawing_selected(self, selector: Selector):
        self._drawed_boxes[selector.name] = selector

    def check_coords(self, selector):
        if selector.is_empty():
            ViewModel.show_message('Область не может быть пустой', 'Ошибка')

    def on_area_selected(self):
        area = self.get_or_create_selector(AREA)
        self.check_coords(area)
        self._area_controller.set_area(area.left_top, area.right_bottom)

    def on_object_selected(self):
        object = self.get_or_create_selector(OBJECT)
        self.check_coords(object)
        # TODO: для улучшения производительности стоит в трекер подавать только выделенную область, а не весь кадр
        area = self.get_or_create_selector(AREA)
        out_of_area = self._area_controller.rect_intersected_borders(object.left_top, object.right_bottom)
        if out_of_area:
            self._view_model.show_message('Нельзя выделять область за зоной слежения', 'Ошибка')
            del self._selectors[OBJECT]
            del self._drawed_boxes[OBJECT]
            return

        frame = self._current_frame
        cropped_frame = Processor.crop_frame(frame, area.left_top, area.right_bottom)
        left_top_offset = object.left_top - area.left_top
        right_bottom_offset = object.right_bottom - area.left_top
        self._tracker.start_tracking(cropped_frame, left_top_offset, right_bottom_offset)
        self._drawed_boxes[OBJECT] = self._tracker
