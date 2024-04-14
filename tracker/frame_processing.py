from collections import deque
from itertools import chain, repeat

import dlib

from eye_tracker.common.abstractions import ProcessBased, RectBased, Drawable
from eye_tracker.common.coordinates import Point, calc_center, get_translation_maxtix, translate_coordinates, \
    get_translation_maxtix_between_resolutions
from eye_tracker.common.logger import logger
from eye_tracker.common.settings import settings
from eye_tracker.model.selector import AreaSelector
from eye_tracker.view.drawing import Processor


class Tracker(RectBased, Drawable, ProcessBased):
    def __init__(self, mean_count=settings.MEAN_COORDINATES_FRAME_COUNT):
        ProcessBased.__init__(self)
        self._mean_count = mean_count
        self.tracker = dlib.correlation_tracker()
        self._denoisers: list[Denoiser] = []
        self._object_length_xy = None
        self._center = None

    @property
    def left_top(self):
        return self._center - self._object_length_xy // 2

    @property
    def right_bottom(self):
        return self._center + self._object_length_xy // 2

    @property
    def center(self):
        return self._center

    def update_center(self):
        left_cur_pos = Point(int(self._denoisers[0].get()), int(self._denoisers[1].get()))
        left_cur_pos = translate_coordinates(self.original_to_cropped_matrix, left_cur_pos)
        right_cur_pos = Point(int(self._denoisers[2].get()), int(self._denoisers[3].get()))
        right_cur_pos = translate_coordinates(self.original_to_cropped_matrix, right_cur_pos)
        center = calc_center(left_cur_pos, right_cur_pos)
        if abs(self.center - center) >= settings.NOISE_THRESHOLD_RANGE:
            self._center = center

    def start_tracking(self, frame, left_top: Point, right_bottom: Point,
                       cropped_width: int, cropped_heigth: int):
        logger.debug('tracking started')
        original_width = int(frame.shape[1])
        original_height = int(frame.shape[0])

        self.cropped_to_original_matrix = get_translation_maxtix_between_resolutions(cropped_width, cropped_heigth,
                                                                                     original_width, original_height)
        self.original_to_cropped_matrix = get_translation_maxtix_between_resolutions(original_width, original_height,
                                                                                     cropped_width, cropped_heigth)
        # needs to be executed before translating coordinates
        self._object_length_xy = Point(abs(left_top.x - right_bottom.x),
                                       abs(left_top.y - right_bottom.y))

        left_top = translate_coordinates(self.cropped_to_original_matrix, left_top)
        right_bottom = translate_coordinates(self.cropped_to_original_matrix, right_bottom)

        frame = Processor.resize_frame_relative(frame, settings.DOWNSCALE_FACTOR)



        scaled_left_top, scaled_right_bottom = \
            (left_top * settings.DOWNSCALE_FACTOR).to_int(), \
            (right_bottom * settings.DOWNSCALE_FACTOR).to_int()

        for coord in chain(left_top, right_bottom):
            self._denoisers.append(Denoiser(coord, mean_count=self._mean_count))

        self._center = calc_center(scaled_left_top, scaled_right_bottom)
        self.tracker.start_track(frame, dlib.rectangle(*scaled_left_top, *scaled_right_bottom))
        self.start()

    def get_tracked_position(self, frame) -> Point:
        frame = Processor.resize_frame_relative(frame, settings.DOWNSCALE_FACTOR)
        self.tracker.update(frame)
        rect = self.tracker.get_position()
        for i, coord in enumerate(map(int, (rect.left() / settings.DOWNSCALE_FACTOR,
                                            rect.top() / settings.DOWNSCALE_FACTOR,
                                            rect.right() / settings.DOWNSCALE_FACTOR,
                                            rect.bottom() / settings.DOWNSCALE_FACTOR
                                            ))):
            self._denoisers[i].add(coord)
        self.update_center()
        return self.center

    def draw_on_frame(self, frame):
        frame = Processor.draw_rectangle(frame, self.left_top, self.right_bottom)
        return Processor.draw_circle(frame, self.center)


class Denoiser:
    def __init__(self, init_value: float, mean_count: int):
        self._count = mean_count
        self._buffer = deque(repeat(init_value, mean_count))
        self._sum = sum(self._buffer)

    def add(self, elem):
        self._sum += elem - self._buffer.popleft()
        self._buffer.append(elem)

    def get(self):
        return self._sum / self._count

class CropZoomer:
    def __init__(self, model):
        self.zoom_area = None
        self.translation_matrix = None
        self._model = model

    def reset_zoom_area(self):
        self.zoom_area = None
        self.translation_matrix = None

    def set_zoom_area(self, area: AreaSelector):
        self.zoom_area = area.calculate_correct_square_points()
        pts = self.zoom_area
        zoom_points = [pts[0], Point(pts[1].x, pts[0].y), pts[1], Point(pts[0].x, pts[1].y)]
        height = self._model.current_frame.shape[0]
        width = self._model.current_frame.shape[1]
        screen_points = [Point(0, 0), Point(width, 0), Point(width, height), Point(0, height)]
        self.translation_matrix = get_translation_maxtix(screen_points, zoom_points)

    def to_zoom_area_coordinates(self, point: Point):
        return translate_coordinates(self.translation_matrix, point)

    def can_crop(self):
        return self.zoom_area is not None and self.translation_matrix is not None

    def crop_zoom_frame(self, frame):
        height = frame.shape[0]
        width = frame.shape[1]
        frame = frame[self.zoom_area[0].y:self.zoom_area[1].y, self.zoom_area[0].x:self.zoom_area[1].x]
        return Processor.resize_frame_absolute(frame, height, width)