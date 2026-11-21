from collections import defaultdict
from dataclasses import dataclass
from math import degrees, atan2
from statistics import mean

import cv2
import numpy as np
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean
from scipy.stats import stats

from tracker.utils.coordinates import Point

MIN_AREA = 9
STANDING_THRESHOLD = 10
MOVING_DISTANCE_THRESHOLD = 25
MIN_ANGLE = 90
CONSISTENCY_THRESHOLD = 0.5


@dataclass
class ContourInfo:
    id: int
    trajectory: list
    areas: list
    last_box: tuple = None
    presence: int = 0
    disappeared: int = 0
    avg_speed: float = 0.0
    total_distance: int = 0
    presence_consistency: float = 1.0
    speed_consistency: float = 1.0
    area_consistency: float = 1.0
    direction_consistency: float = 1.0
    general_consistency: float = 1.0

    def __post_init__(self):
        if self.last_box is None:
            self.last_box = (Point(0, 0), Point(0, 0))

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
        self.objects = {}
        self.object_id = 0

    def calculate_angle(self, p1: Point, p2: Point, p3: Point) -> float:
        angle = degrees(atan2(p3.y - p2.y, p3.x - p2.x) - atan2(p1.y - p2.y, p1.x - p2.x))
        return abs(angle)

    def track_moving_objects(self, frames, min_angle=MIN_ANGLE,
                             standing_threshold=STANDING_THRESHOLD,
                             moving_distance_threshold=MOVING_DISTANCE_THRESHOLD,
                             min_area=MIN_AREA):
        for frame_index, contours in enumerate(frames):
            current_frame_objects = set()

            for cnt in contours:
                M = cv2.moments(cnt)
                if M['m00'] < min_area:
                    continue
                cX = int(M['m10'] / M['m00'])
                cY = int(M['m01'] / M['m00'])
                points = cnt[:, 0, :]

                left = points[np.argmin(points[:, 0])][0]
                top = points[np.argmin(points[:, 1])][1]
                right = points[np.argmax(points[:, 0])][0]
                bottom = points[np.argmax(points[:, 1])][1]
                current_frame_objects.add(ObjectInfo(
                    Point(cX, cY), M['m00'],
                    Point(float(left), float(top)),
                    Point(float(right), float(bottom))
                ))

            if frame_index == 0:
                for obj in current_frame_objects:
                    self.objects[self.object_id] = ContourInfo(
                        self.object_id, [obj.coords], areas=[obj.area]
                    )
                    self.object_id += 1
            else:
                matched_known_objects = {}
                for obj in current_frame_objects:
                    matched = None
                    for obj_id, contour_info in self.objects.items():
                        trajectory = contour_info.trajectory
                        if trajectory:
                            if trajectory[-1] == obj.coords:
                                matched = contour_info
                                break
                            else:
                                dist = euclidean(trajectory[-1].to_tuple(), obj.coords.to_tuple())
                                if dist <= standing_threshold:
                                    matched = contour_info
                                    break
                                elif dist < moving_distance_threshold:
                                    if len(trajectory) >= 3:
                                        angle = self.calculate_angle(
                                            trajectory[-3], trajectory[-2], obj.coords
                                        )
                                        if angle >= min_angle:
                                            matched = contour_info
                                            break
                                    else:
                                        matched = contour_info
                                        break
                    if matched is not None:
                        if matched.trajectory[-1] != obj.coords:
                            matched.trajectory.append(obj.coords)
                        matched.areas.append(obj.area)
                        matched.last_box = (obj.left_top, obj.right_bottom)
                        matched.presence += 1
                        matched_known_objects[matched.id] = matched
                    else:
                        self.objects[self.object_id] = ContourInfo(
                            self.object_id, [obj.coords], [obj.area]
                        )
                        self.object_id += 1

                unmatched = set(self.objects.values()) - set(matched_known_objects.values())
                for o in unmatched:
                    o.disappeared += 1

        return self.objects

    def calculate_objects_characteristics(self, objects):
        for o in objects.values():
            o.presence_consistency = 1 - o.disappeared / (o.presence + 1)
            o.presence_consistency = max(0.0, o.presence_consistency)

            avg_area = sum(o.areas) / len(o.areas)
            speeds = [o.trajectory[i].calc_distance(o.trajectory[i - 1])
                      for i in range(1, len(o.trajectory))]

            o.avg_speed = sum(speeds) / len(speeds) if speeds else 0.0
            o.speed_consistency = mean(
                min(o.avg_speed, s) / max(o.avg_speed, s) for s in speeds
            ) if speeds else 0.0
            o.area_consistency = mean(
                min(avg_area, a) / max(avg_area, a) for a in o.areas
            ) if o.areas else 0.0

            o.total_distance = o.trajectory[-1].calc_distance(o.trajectory[0]) if len(o.trajectory) > 1 else 0
            if o.total_distance:
                x = np.array([t.x for t in o.trajectory])
                y = np.array([t.y for t in o.trajectory])
                try:
                    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
                except ValueError:
                    slope, intercept, r_value, p_value, std_err = stats.linregress(y, x)
                o.direction_consistency = r_value ** 2
            else:
                o.direction_consistency = 0.0

            o.general_consistency = (
                1.75 * o.presence_consistency +
                1.25 * o.direction_consistency +
                0.75 * o.speed_consistency +
                0.25 * o.area_consistency
            ) / 4

    def filter_objects(self, objects, consistency_threshold=CONSISTENCY_THRESHOLD):
        return {
            i: o for i, o in objects.items()
            if o.general_consistency > consistency_threshold
            and o.avg_speed > 0
            and o.total_distance > 1
        }

    def translate_trajectories_relative(self, trajectory: list):
        first = trajectory[0]
        return [(t - first).to_tuple() for t in trajectory]

    def stick_close_objects(self, objects: dict):
        sticked = defaultdict(set)
        for obj_id in objects:
            for other_id in objects:
                if obj_id != other_id:
                    dist, path = fastdtw(
                        np.array(objects[obj_id].trajectory),
                        np.array(objects[other_id].trajectory),
                        dist=euclidean
                    )
                    if dist < (len(objects[obj_id].trajectory) + len(objects[other_id].trajectory)) * 3:
                        sticked[obj_id].add(other_id)
        if not sticked:
            return {i: set() for i in objects}
        id_max = max(sticked.keys(), key=lambda k: len(sticked[k]))
        max_sticked_element = sticked[id_max]
        to_remove = []
        for obj_id in sticked:
            if obj_id in max_sticked_element:
                for elem in sticked[obj_id]:
                    max_sticked_element.add(elem)
                to_remove.append(obj_id)
        for i in to_remove:
            del sticked[i]
        return sticked
