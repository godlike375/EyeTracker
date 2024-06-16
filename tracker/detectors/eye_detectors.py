from collections import deque
from dataclasses import dataclass

import cv2
import numpy

from tracker.detectors.detectors import EyeDetector
from tracker.utils.coordinates import Point
from tracker.utils.denoise import MovingAverageDenoiser


@dataclass
class HaarModel:
    min_size: int
    scale_factor: float
    neighbours: int


class HaarHoughEyeDetector(EyeDetector):
    def mainloop(self):
        self.x1 = MovingAverageDenoiser(0, 10)
        self.x2 = MovingAverageDenoiser(0, 10)
        self.y1 = MovingAverageDenoiser(0, 10)
        self.y2 = MovingAverageDenoiser(0, 10)
        self.eye_cascade = cv2.CascadeClassifier('haarcascade_eye.xml')
        self.models = [HaarModel(19, 2.65, 1), HaarModel(22, 1.35, 2)] #, , , ] HaarModel(33, 1.65, 1)
        self.frames_count = 7
        self.previous_eyes = deque(maxlen=self.frames_count)
        self.previous_eyes_levels = deque(maxlen=self.frames_count)
        manual_x, manual_y, manual_x2, manual_y2 = self.eye_box[0], self.eye_box[1], self.eye_box[2], self.eye_box[3]
        self.eye_coordinates[0], self.eye_coordinates[1], self.eye_coordinates[2], self.eye_coordinates[3] = \
            manual_x, manual_y, manual_x2, manual_y2
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
                if ex >= mx and ey >= my and ex + ew <= mx + mw and ey + eh <= my + mh:
                    merged = True
                    # if i < frame_eyes.size:
                    merged_boxes[j] = (ex, ey, ew, eh, (confidence + mconfidence) * 6)
                    # else:
                    #     merged_boxes[j] = (mx, my, mw, mh, (confidence + mconfidence) * 3)
                    # break
                # TODO: можно в близких рамках брать минимальные по размеру, т.к. они более точные и тогда меньше будут прыгать
                center = Point(ex + ew // 2, ey + eh // 2)
                mcenter = Point(mx + mw // 2, my + mh // 2)
                distance = center.calc_distance(mcenter)
                if distance < (ew + eh + mw + mh) / 5:
                    if i < frame_eyes.size:
                        merged_boxes[j] = (
                            (ex if ew < mw else mx), (ey if eh < mh else my), min(ew, mw), min(eh, mh),
                            (confidence + mconfidence) * 3)
                    else:
                        if distance < (ew + eh + mw + mh) / self.frames_count * 3:
                            merged_boxes[j] = (
                                mx, my, mw, mh, (confidence + mconfidence) * 2)
                    merged = True
                    break
            if not merged:
                merged_boxes.append((ex, ey, ew, eh, confidence))

        sorted_boxes = sorted(merged_boxes, key=lambda i: i[4], reverse=True)

        best_length = min(1, len(sorted_boxes))
        final_boxes = sorted_boxes[:best_length]
        manual_x, manual_y, manual_x2, manual_y2 = self.eye_box[0], self.eye_box[1], self.eye_box[2], self.eye_box[3]
        if final_boxes:
            eye_box = final_boxes[0]
            self.x1.add(manual_x+eye_box[0])
            self.y1.add(manual_y+eye_box[1])
            self.x2.add(manual_x + eye_box[0] + eye_box[2])
            self.y2.add(manual_y + eye_box[1] + eye_box[3])
            self.eye_coordinates[:] = int(self.x1.get()), int(self.y1.get()), int(self.x2.get()), int(self.y2.get())
        else:
            self.eye_coordinates[0], self.eye_coordinates[1], self.eye_coordinates[2], self.eye_coordinates[3] =\
            manual_x, manual_y, manual_x2, manual_y2

