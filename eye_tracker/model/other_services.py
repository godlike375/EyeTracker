from collections import defaultdict
from dataclasses import dataclass
from functools import partial
from math import degrees, atan2
from statistics import mean
from time import time, sleep

import cv2
import numpy as np
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean
from scipy.stats import stats

from eye_tracker.common.abstractions import ProcessBased, Calibrator
from eye_tracker.common.coordinates import Point

from eye_tracker.common.logger import logger
from eye_tracker.common.settings import AREA, OBJECT, settings, MIN_THROTTLE_DIFFERENCE
from eye_tracker.common.thread_helpers import threaded
from eye_tracker.model.selector import AreaSelector, ObjectSelector
from eye_tracker.view import view_output
from eye_tracker.view.view_model import START_TRACKING_MENU_NAME
from eye_tracker.view.drawing import Processor
from tracker.utils.image_processing import resize_frame_relative

PERCENT_FROM_DECIMAL = 100


class OnScreenService:
    def __init__(self, model):
        self.on_screen_selectors = dict()  # {name: Selector}
        self._model = model

    def add_selector(self, selector, name):
        self.on_screen_selectors[name] = selector

    def remove_selector(self, name):
        if name not in self.on_screen_selectors:
            return
        del self.on_screen_selectors[name]
        self._model.state_control.change_state(f'{name} selected', happened=False)
        if OBJECT in name:
            self._model.tracker.cancel()

    def get_selector(self, name):
        return self.on_screen_selectors.get(name)

    def selector_exists(self, name):
        return name in self.on_screen_selectors

    def common_processing(self, frame):
        frame = Processor.resize_to_minimum(frame)
        processed = self._draw_active_objects(frame)
        return processed

    def prepare_image(self, frame):
        return Processor.frame_to_image(frame)

    def _draw_active_objects(self, frame):
        for obj in self.on_screen_selectors.values():
            frame = obj.draw_on_frame(frame)
        return frame


class SelectingService(ProcessBased):
    def __init__(self, area_selected_callback, object_selected_callback, model, screen: OnScreenService, view_model):
        self._on_area_selected = area_selected_callback
        self._on_object_selected = object_selected_callback
        self._model = model
        self._screen = screen
        self._view_model = view_model

    def load_selected_area(self, area):
        area_selector = AreaSelector(AREA, self._on_area_selected, area)
        if area_selector.is_empty:
            return
        area_selector._is_done = True
        area_selector._in_progress = False
        self._screen.add_selector(area_selector, AREA)
        self._on_area_selected()

    def check_emptiness(self, selector, name):
        if selector is None or selector.is_empty:
            logger.warning('selected area is too small in size')
            view_output.show_error('Выделенная область слишком мала или некорректно выделена.', 'Ошибка')
            self._screen.remove_selector(name)

    def create_selector(self, name, call_func_after_selection=None):
        logger.debug(f'creating new selector {name}')

        on_selected = self._on_object_selected if OBJECT in name else self._on_area_selected

        if call_func_after_selection is not None:
            on_selected = partial(on_selected, call_func_after_selection)

        selector = ObjectSelector(name, on_selected) if OBJECT in name else AreaSelector(name, on_selected)
        self._screen.add_selector(selector, name)
        self._view_model.set_menu_state('all', 'disabled')
        return selector

    def selecting_is_done(self, name):
        return self._screen.selector_exists(name) and self._screen.get_selector(name).is_done

    def selecting_in_progress(self, name):
        return self._screen.selector_exists(name) and self._screen.get_selector(name).in_progress

    def cancel(self):
        self._model.state_control.change_state('enter pressed', False)
        for name in (AREA, OBJECT):
            if not self._screen.selector_exists(name):
                continue
            if not self.selecting_is_done(name):
                self._screen.get_selector(name).cancel()
                self._screen.remove_selector(name)

    def check_selected_correctly(self, name):
        selector = self._screen.get_selector(name)
        self.check_emptiness(selector, name)
        if not self.selecting_is_done(name):
            return False, None
        return True, selector

    def is_object_selection_allowed(self, select_in_calibrating):
        if select_in_calibrating:
            return True

        if self.selecting_is_done(OBJECT):
            confirm = view_output.ask_confirmation('Выделенный объект перестанет отслеживаться. Продолжить?')
            if not confirm:
                return False

        return self.selecting_is_done(AREA)

    def is_area_selection_allowed(self, dont_reselect_area):
        # TODO: поправить логику и сделать без костылей вроде этого
        if dont_reselect_area:
            return False

        tracking_stop_question = ''
        if self.selecting_is_done(OBJECT):
            tracking_stop_question = 'Слежение за целью будет остановлено. '
        if self.selecting_is_done(AREA):
            confirm = view_output.ask_confirmation(f'{tracking_stop_question}'
                                                   f'Выделенная область будет стёрта. Продолжить?')
            if not confirm:
                return False
        self._screen.remove_selector(OBJECT)
        self._model.state_control.change_state('coordinate system calibrated', happened=False)
        return True

    def try_create_selector(self, name, reselect_while_calibrating=False, additional_callback=None):

        if OBJECT in name:
            if not self.is_object_selection_allowed(reselect_while_calibrating):
                return

        if AREA in name:
            if not self.is_area_selection_allowed(dont_reselect_area=reselect_while_calibrating):
                return

        self._screen.remove_selector(name)

        if OBJECT in name:
            self._model.state_control.change_state('enter pressed', happened=False)

        return self.create_selector(name, additional_callback)


@dataclass
class EventCheck:
    __slots__ = ['name', 'happened', 'tip']
    name: str
    happened: bool
    tip: str


class StateMachine:
    def __init__(self, view_model):
        self._view_model = view_model
        # Расположены в порядке приоритета от наибольшего к наименьшему
        self._all_events = (
            EventCheck('enter pressed', True, 'Выделите объект, отрегулируйте стрелками положение и нажмите Enter'
                                              '\n для подтверждения выделения'),
            EventCheck('calibrating finished', True, 'Происходит процесс калибровки'),
            EventCheck('camera connected', False, 'Подключите камеру'),
            EventCheck('laser connected', False, 'Подключите контроллер лазера'),
            EventCheck('laser calibrated', False, 'Откалибруйте лазер'),
            #EventCheck('noise threshold calibrated', False, 'Откалибруйте шумоподавление'),
            EventCheck('coordinate system calibrated', False,
                       'Откалибруйте координатную систему или выделите область вручную'),
            EventCheck('object selected', False, 'Всё готово к отслеживанию')
        )

    def change_state(self, event_name: str, happened=True):
        if event_name == 'coordinate system changed':
            for event in self._all_events[:2]:
                event.happened = True
            for event in self._all_events[6:]:
                event.happened = False

        for event in self._all_events:
            if event_name == event.name:
                event.happened = happened

        prioritized = self._most_prioritized_event()
        if prioritized is None:
            self._view_model.set_tip('')
            return
        self._view_model.set_tip(prioritized.tip)

        if prioritized.name == 'object selected':
            self._view_model.set_menu_state(START_TRACKING_MENU_NAME, 'normal')
        else:
            self._view_model.set_menu_state(START_TRACKING_MENU_NAME, 'disabled')

    def _most_prioritized_event(self):
        for event in self._all_events:
            if not event.happened:
                return event


class NoiseThresholdCalibrator(ProcessBased, Calibrator):
    CALIBRATION_THRESHOLD_STEP = 0.25

    # В течение settings.THRESHOLD_CALIBRATION_DURATION секунд цель трекинга не должна двигаться
    def __init__(self, model, view_model):
        super().__init__()
        self._last_position = None
        self._last_timestamp = time()
        self._model = model
        self._view_model = view_model
        self._delay_sec = 1 / settings.FPS_PROCESSED
        self._progress = 0

    def _is_calibration_successful(self, center):
        if self._last_position is None:
            self._last_position = center
            self._last_timestamp = time()
            return False
        if not (center == self._last_position):
            settings.NOISE_THRESHOLD_RANGE += NoiseThresholdCalibrator.CALIBRATION_THRESHOLD_STEP
            self._last_position = center
            self._last_timestamp = time()
            return False
        elif time() - self._last_timestamp > settings.THRESHOLD_CALIBRATION_DURATION:
            self.finish()
            return True

    def _calibration_progress(self):
        return int(((time() - self._last_timestamp) / settings.THRESHOLD_CALIBRATION_DURATION) * PERCENT_FROM_DECIMAL)

    def _calibrating_finish(self, center):
        if self._is_calibration_successful(center):
            return True

        progress_value = self._calibration_progress()
        if abs(self._progress - progress_value) > MIN_THROTTLE_DIFFERENCE:
            self._view_model.set_progress(progress_value)

    @threaded
    def calibrate(self):
        self._model.state_control.change_state('calibrating finished', happened=False)
        settings.NOISE_THRESHOLD_RANGE = 0.0
        object = self._model.screen.get_selector(OBJECT)
        while True:
            if not self.in_progress:
                exit()
            sleep(self._delay_sec)
            if self._calibrating_finish(object.center):
                break
        self._on_calibrated()

    def _on_calibrated(self):
        self._model.tracker.cancel()
        self._model.screen.remove_selector(OBJECT)
        self._model.try_restore_previous_area()
        self._model.state_control.change_state('noise threshold calibrated')
        settings.NOISE_THRESHOLD_RANGE = round(settings.NOISE_THRESHOLD_RANGE, 3)
        view_output.show_message('Калибровка шумоподавления успешно завершена.')

    def cancel(self):
        if not self.in_progress:
            return
        super().cancel()
        settings.NOISE_THRESHOLD_RANGE = 0.0
        self._view_model.set_menu_state('all', 'normal')

    def finish(self):
        super().finish()
        self._model.state_control.change_state('calibrating finished')
        self._view_model.set_menu_state('all', 'normal')

@dataclass
class ContourInfo:
    id: int
    trajectory: list[Point]
    areas: list[float]
    last_box: tuple[Point, Point] = Point(0, 0), Point(0, 0)
    presence: int = 0
    disappeared: int = 0
    avg_speed: float = 0.0
    total_distance: int = 0
    presence_consistency: float = 1.0
    speed_consistency: float = 1.0
    area_consistency: float = 1.0
    direction_consistency: float = 1.0
    general_consistency: float = 1.0

    def __hash__(self):
        return hash(self.id)

@dataclass
class ObjectInfo:
    coords: Point
    area: float
    left_top: Point
    right_bottom: Point

    def __hash__(self):
        return hash(self.coords.to_tuple())


class ContourTracker:
    def __init__(self):
        self.objects: dict[int, ContourInfo] = {}  # {id: ContourInfo}
        self.object_id = 0

    def calculate_angle(self, p1: Point, p2: Point, p3: Point) -> float:
        angle = degrees(atan2(p3.y - p2.y, p3.x - p2.x) - atan2(p1.y - p2.y, p1.x - p2.x))
        return abs(angle)

    def track_moving_objects(self, frames, min_angle=90, standing_threshold=10, moving_distance_threshold=25, min_area=9):
        for frame_index, contours in enumerate(frames):
            current_frame_objects: set[ObjectInfo] = set()

            for cnt in contours:
                M = cv2.moments(cnt)
                if M['m00'] < min_area:
                    continue
                cX = int(M['m10'] / M['m00'])
                cY = int(M['m01'] / M['m00'])
                points = cnt[:, 0, :]  # Извлекаем только x и y координаты

                # Находим верхнюю левую и правую нижнюю точки
                left = points[np.argmin(points[:, 0])][0]  # Минимум по x и y
                top = points[np.argmin(points[:, 1])][1]  # Минимум по x и y
                right = points[np.argmax(points[:, 0])][0]
                bottom = points[np.argmax(points[:, 1])][1]
                current_frame_objects.add(ObjectInfo(Point(cX, cY), M['m00'],
                                                     Point(float(left), float(top)),
                                                     Point(float(right), float(bottom))
                                                     ))

            matched_known_objects = {}

            if frame_index == 0:
                for obj in current_frame_objects:
                    self.objects[self.object_id] = ContourInfo(self.object_id, [obj.coords], areas=[obj.area])
                    self.object_id += 1
            else:
                for obj in current_frame_objects:
                    matched = None
                    frame_unmatched = obj
                    for obj_id, contour_info in self.objects.items():
                        trajectory = contour_info.trajectory
                        if trajectory:
                            same_as_last = trajectory[-1] == obj.coords
                            if same_as_last:
                                matched = contour_info
                                break
                            else:
                                distance_from_last = euclidean(trajectory[-1].to_tuple(), obj.coords.to_tuple())
                                if distance_from_last <= standing_threshold:
                                    matched = contour_info
                                    break
                                elif distance_from_last < moving_distance_threshold:
                                    if len(trajectory) >= 3:
                                        angle = self.calculate_angle(trajectory[-3], trajectory[-2], obj.coords)
                                        if angle >= min_angle:
                                            matched = contour_info
                                            break
                                    else:
                                        matched = contour_info
                                        break
                    if matched is not None:
                        if matched.trajectory[-1] != frame_unmatched.coords:
                            matched.trajectory.append(frame_unmatched.coords)
                        matched.areas.append(frame_unmatched.area)
                        matched.last_box = (frame_unmatched.left_top, frame_unmatched.right_bottom,)
                        matched.presence += 1
                        matched_known_objects[matched.id] = matched
                    else:
                        self.objects[self.object_id] = ContourInfo(self.object_id, [obj.coords], [frame_unmatched.area])
                        self.object_id += 1

            unmatched_known_objects = set(self.objects.values()) - set(matched_known_objects.values())
            for o in unmatched_known_objects:
                o.disappeared += 1

        # Filter stable and large contours
        return self.objects

    def calculate_objects_characteristics(self, objects):
        for id, o in objects.items():
            o.presence_consistency = 1 - o.disappeared / (o.presence + 1)
            o.presence_consistency = 0.0 if o.presence_consistency < 0 else o.presence_consistency
            avg_area = sum(o.areas) / len(o.areas)
            speeds = []

            for i in range(1, len(o.trajectory)):
                distance = o.trajectory[i].calc_distance(o.trajectory[i - 1])
                speeds.append(distance)

            avg_speed = sum(speeds) / len(speeds) if speeds else 0.0
            o.avg_speed = avg_speed
            consistent_speed = mean(min(avg_speed, speed) / max(avg_speed, speed) for speed in speeds) if speeds else 0
            consistent_area = mean(min(avg_area, area) / max(avg_area, area) for area in o.areas)
            o.speed_consistency = consistent_speed
            o.area_consistency = consistent_area

            o.total_distance = o.trajectory[-1].calc_distance(o.trajectory[0]) if len(o.trajectory) > 1 else 0
            if o.total_distance:
                x = []
                y = []
                for t in o.trajectory:
                    x.append(t.x)
                    y.append(t.y)
                x = np.array(x)
                y = np.array(y)
                try:
                    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
                except ValueError:
                    slope, intercept, r_value, p_value, std_err = stats.linregress(y, x)
                consistent_direction = r_value ** 2
                o.direction_consistency = consistent_direction
            else:
                o.direction_consistency = 0.0
            o.general_consistency = (1.75 * o.presence_consistency + 1.25 * o.direction_consistency
                                       + 0.75 * o.speed_consistency + 0.25 * o.area_consistency) / 4

    def filter_objects(self, objects, consistency_threshold=0.5):
        #ordered_objects = sorted(objects.values(), key=lambda o: o.general_consistency, reverse=True)
        #for o in ordered_objects:
            #print(o.id, o.presence_consistency, o.direction_consistency, o.speed_consistency, o.general_consistency)
        return {i: o for i, o in objects.items()
                if o.general_consistency > consistency_threshold
                and o.avg_speed > 0
                and o.total_distance > 1}

    def translate_trajectories_relative(self, trajectory: list[Point]):
        first = trajectory[0]
        return [(t - first).to_tuple() for t in trajectory]

    def stick_close_objects(self, objects: dict[int, ContourInfo]):
        sticked = defaultdict(set)
        for id in objects:
            for id2 in objects:
                if id != id2:
                    distance, path = fastdtw(np.array(objects[id].trajectory),
                                             np.array(objects[id2].trajectory), dist=euclidean)
                    if distance < (len(objects[id].trajectory) + len(objects[id2].trajectory)) * 3:
                        sticked[id].add(id2)
        if not len(sticked):
            return {i: set() for i in objects}
        id_max = max(sticked.keys(), key=lambda k: len(sticked[k]))
        max_sticked_element = sticked[id_max]
        to_remove = []
        for id in sticked:
            if id in max_sticked_element:
                for elem in sticked[id]:
                    max_sticked_element.add(elem)
                to_remove.append(id)

        for i in to_remove:
            del sticked[i]
        return sticked


class CoordinateSystemCalibrator(ProcessBased, Calibrator):
    def __init__(self, model: 'Orchestrator', view_model):
        super().__init__()
        self._model = model
        self._view_model = view_model
        self._laser_borders = model.laser.laser_borders
        self._delay_sec = 1 / settings.FPS_VIEWED
        self._area = None

    def get_object_center(self, object):
        return object.center

    def find_laser_coordinates(self):
        current_point = self._model.laser.current_position
        max_dist_point = max(self._laser_borders, key=lambda x: x.calc_distance(current_point))
        self._model.laser.set_new_position(max_dist_point)
        recorded_frames = []
        while not self._model.laser.controller_is_ready():
            frame = self._model.raw_frame
            frame = resize_frame_relative(frame, 0.5)
            frame = cv2.medianBlur(frame, 3)
            recorded_frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            sleep(self._delay_sec)
        start_threshold = 243
        step = 3
        objects = {}
        sticked_objects = None

        while start_threshold > 96:
            extracted_contours = []
            for frame in recorded_frames:
                mask = cv2.threshold(np.copy(frame), start_threshold, 255, cv2.THRESH_BINARY)[1]
                if mask.max() == 0:
                    start_threshold -= step
                    print(start_threshold)
                    break
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
                mask = cv2.erode(mask, kernel, iterations=1)
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
                mask = cv2.dilate(mask, kernel, iterations=1)
                #cv2.imshow('test', frame)
                #cv2.waitKey(1)
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                extracted_contours.append(contours)
            tr = ContourTracker()
            objects = tr.track_moving_objects(extracted_contours)
            tr.calculate_objects_characteristics(objects)
            objects = tr.filter_objects(objects)
            if objects:
                for id in objects:
                    objects[id].trajectory = tr.translate_trajectories_relative(objects[id].trajectory)

                sticked_objects: dict[int, list[int]] = tr.stick_close_objects(objects)
                if len(sticked_objects) > 1:
                    start_threshold += step // 2
                    continue
                break
            else:
                start_threshold -= step

        if not sticked_objects:
            view_output.show_error('Не удалось автоматически определить позицию лазера на основе имеющихся изображений')
            raise Exception('Не удалось автоматически определить позицию лазера на основе имеющихся изображений')
        ids = list(sticked_objects.keys())
        ids.extend([id for id in sticked_objects[ids[0]]])
        final_contours = [objects[id] for id in ids]
        min_left = min(final_contours, key=lambda o: o.last_box[0].x).last_box[0].x * 2
        min_top = min(final_contours, key=lambda o: o.last_box[0].y).last_box[0].y * 2
        max_right = max(final_contours, key=lambda o: o.last_box[1].x).last_box[1].x * 2
        max_bottom = max(final_contours, key=lambda o: o.last_box[1].y).last_box[1].y * 2
        return Point(min_left, min_top).to_int(), Point(max_right, max_bottom).to_int()


    @threaded
    def calibrate(self):
        self._model.state_control.change_state('calibrating finished', happened=False)
        object = self._model.screen.get_selector(OBJECT)
        area = self._model.selecting.create_selector(AREA)
        progress = 0
        self._wait_for_controller_ready()

        for point in self._laser_borders:
            self._model.laser.set_new_position(point)
            logger.debug(f'setting laser position {point.x, point.y}')
            self._wait_for_controller_ready()
            area_point = self.get_object_center(object)
            area.left_button_click(area_point)
            progress += 25
            self._view_model.set_progress(progress)

        self._area = area
        self._on_calibrated()

    def _wait_for_controller_ready(self):
        while not self._model.laser.controller_is_ready():
            if not self.in_progress:
                exit()
            sleep(self._delay_sec)

    def _on_calibrated(self):
        self._model.screen.remove_selector(OBJECT)

        self._view_model.set_progress(0)
        self._view_model.progress_bar_set_visibility(False)
        self._model.state_control.change_state('object selected', happened=False)
        if self._area.is_empty:
            view_output.show_error('Необходимо повторить калибровку на более близком расстоянии '
                                   'камеры от области лазера.')
            self.cancel()
            return

        self._model.area_controller.set_area(self._area, self._laser_borders)
        view_output.show_message('Калибровка координатной системы успешно завершена.')
        self.finish()
        self._model.center_laser()

    def cancel(self):
        if not self.in_progress:
            return
        super().cancel()
        self._view_model.set_menu_state('all', 'normal')

    def finish(self):
        super().finish()
        self._model.state_control.change_state('calibrating finished')
        self._view_model.set_menu_state('all', 'normal')
