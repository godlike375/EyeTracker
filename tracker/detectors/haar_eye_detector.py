from collections import deque
from dataclasses import dataclass
from multiprocessing import Array

import cv2
import numpy

from tracker.detectors.detectors import Detector, EyeDetector
from tracker.utils.coordinates import Point, int_avg, close_to
from tracker.utils.denoise import MovingAverageDenoiser
from tracker.utils.shared_objects import SharedBox


@dataclass
class HaarModel:
    min_size: int
    scale_factor: float
    neighbours: int

@dataclass
class EyeAveragedBox:
    x1: MovingAverageDenoiser = MovingAverageDenoiser(2)
    x2: MovingAverageDenoiser = MovingAverageDenoiser(2)
    y1: MovingAverageDenoiser = MovingAverageDenoiser(2)
    y2: MovingAverageDenoiser = MovingAverageDenoiser(2)

    def add_if_diff_from_avg(self, x, y, w, h):
        self.x1.add_if_diff_from_avg(x)
        self.y1.add_if_diff_from_avg(y)
        self.x2.add_if_diff_from_avg(w)
        self.y2.add_if_diff_from_avg(h)

    @property
    def left_top(self):
        return self.x1, self.y1

    @property
    def right_bottom(self):
        return self.x2, self.y2


class HaarEyeValidator(EyeDetector):
    def mainloop(self):
        self.left_box = EyeAveragedBox()
        self.right_box = EyeAveragedBox()
        self.eye_cascade = cv2.CascadeClassifier('haarcascade_eye.xml')
        self.models = [HaarModel(19, 2.65, 1), HaarModel(22, 1.35, 2)] #, , , ] HaarModel(33, 1.65, 1)
        self.frames_count = 14
        self.previous_eyes = deque(maxlen=self.frames_count)
        self.previous_eyes_levels = deque(maxlen=self.frames_count)
        super().mainloop()

    def get_outer_boxes(self, eyes):
        # Создаем список для результирующих рамок
        new_eye_frames = []

        # Проходим по списку рамок и удаляем внешние
        for (x, y, w, h) in eyes:
            # Проверяем, есть ли внутри рамки другие рамки
            is_outer_frame = True
            for (x2, y2, w2, h2) in eyes:
                if (x2, y2, w2, h2) != (x, y, w, h) and x2 >= x and y2 >= y and x2 + w2 <= x + w and y2 + h2 <= y + h:
                    is_outer_frame = False
                    break

            # Если это внешняя рамка, добавляем ее в результирующий список
            if is_outer_frame:
                new_eye_frames.append((x, y, w, h))

        return new_eye_frames

    def haar_detect(self, gray: numpy.ndarray):
        frame_eyes = numpy.empty(shape=(0, 4), dtype=int)
        frame_eye_levels = numpy.empty(shape=(0,), dtype=int)
        for model in self.models:
            actual_min_size = int(model.min_size * model.scale_factor)
            new_eyes, _, new_eye_levels = self.eye_cascade.detectMultiScale3(gray,
                                                                             scaleFactor=model.scale_factor,
                                                                             minNeighbors=model.neighbours,
                                                                             minSize=(actual_min_size, actual_min_size),
                                                                             outputRejectLevels=True)

            if type(new_eyes) is tuple:
                continue  # Не нашли глаз

            try:
                frame_eyes = numpy.append(frame_eyes, new_eyes.astype(int), axis=0)
                frame_eye_levels = numpy.append(frame_eye_levels, new_eye_levels, axis=0)
            except:
                continue

        return frame_eyes, frame_eye_levels

    def detect(self, raw: numpy.ndarray):
        gray = self.get_eye_frame(raw)
        frame_eyes, frame_eye_levels = self.haar_detect(gray)
        total_eyes, total_eye_levels = frame_eyes.copy(), frame_eye_levels.copy()
        for eyes in self.previous_eyes:
            total_eyes = numpy.append(total_eyes, eyes, axis=0)
        for eye_levels in self.previous_eyes_levels:
            total_eye_levels = numpy.append(total_eye_levels, eye_levels, axis=0)

        if len(self.previous_eyes) == self.frames_count:
            self.previous_eyes.popleft()
            self.previous_eyes_levels.popleft()
        self.previous_eyes.append(frame_eyes)
        self.previous_eyes_levels.append(frame_eye_levels)

        zipped = [(*total_eyes[i], total_eye_levels[i]) for i in range(len(total_eyes))]

        merged_boxes = []
        for i, (ex, ey, ew, eh, confidence) in enumerate(zipped):
            merged = False
            for j, (mx, my, mw, mh, mconfidence) in enumerate(merged_boxes):
                center = Point(int_avg(ex, ew), int_avg(ey, eh))
                mcenter = Point(int_avg(mx, mw), int_avg(my, mh))
                distance = center.calc_distance(mcenter)

                if ex >= mx and ey >= my and ex + ew <= mx + mw and ey + eh <= my + mh:
                    merged = True
                    # if i < frame_eyes.size:
                    if distance < (ew + eh + mw + mh) / 3.25:
                        merged_boxes[j] = (ex, ey, ew, eh, (confidence + mconfidence) * 10)
                    else:
                        merged_boxes[j] = (int_avg(ex, mx), int_avg(ey, my), int_avg(ew, mw), int_avg(eh, mh),
                                           (confidence + mconfidence) * 6.5)
                    # else:
                    #     merged_boxes[j] = (mx, my, mw, mh, (confidence + mconfidence) * 3)
                    # break
                if distance < (ew + eh + mw + mh) / 4.25:
                    if i < frame_eyes.size:
                        merged_boxes[j] = (
                            (ex if ew < mw else mx), (ey if eh < mh else my),
                            close_to(ew, mw, 3), close_to(eh, mh, 3),
                            (confidence + mconfidence) * 5)
                    else:
                        if distance < (ew + eh + mw + mh) / (self.frames_count / 1.25):
                            merged_boxes[j] = (
                                close_to(ex, mx), close_to(ey, my), close_to(ew, mw), close_to(eh, mh),
                                (confidence + mconfidence) * 1.75)
                    merged = True
                    break
            if not merged:
                merged_boxes.append((ex, ey, ew, eh, confidence))

        sorted_boxes = sorted(merged_boxes, key=lambda i: i[4], reverse=True)

        final_boxes = sorted_boxes[:2]
        if len(final_boxes) == 2:
            left_eye = final_boxes[0] if final_boxes[0][0] < final_boxes[1][0] else final_boxes[1]
            right_eye = final_boxes[0] if final_boxes[0][0] > final_boxes[1][0] else final_boxes[1]
            self.left_box.add_if_diff_from_avg(*left_eye[:-1])
            self.right_box.add_if_diff_from_avg(*right_eye[:-1])

            x1, y1 = self.left_box.left_top
            x2, y2 = self.left_box.right_bottom
            self.left_eye.left_top.array[:] = int(x1.get()), int(y1.get())
            self.left_eye.right_bottom.array[:] = int(x2.get()), int(y2.get())

            x1, y1 = self.right_box.left_top
            x2, y2 = self.right_box.right_bottom
            self.right_eye.left_top.array[:] = int(x1.get()), int(y1.get())
            self.right_eye.right_bottom.array[:] = int(x2.get()), int(y2.get())
        else:
            self.left_eye.invalidate()
            self.right_eye.invalidate()

