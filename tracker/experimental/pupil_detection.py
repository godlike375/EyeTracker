from collections import deque

import cv2
import numpy
import numpy as np
from dataclasses import dataclass

from tracker.utils.coordinates import Point

cap = cv2.VideoCapture(1)
#cap = cv2.VideoCapture(r'C:\Users\godlike\Desktop\макаки2\bandicam 2024-05-23 05-30-57-597.mp4')
#cap = cv2.VideoCapture(r'C:\Users\godlike\Desktop\Видео_макаки\снизу_близко.mp4')
#cap = cv2.VideoCapture(r'C:\Users\godlike\Desktop\Видео_макаки\сверху.mp4')
eye_cascade = cv2.CascadeClassifier('../haarcascade_eye.xml')

@dataclass
class HaarModel:
    min_size: int
    scale_factor: float
    neighbours: int

frames_count = 3
previous_eyes = deque(maxlen=frames_count)
previous_eyes_levels = deque(maxlen=frames_count)
models = [ HaarModel(19, 2.65, 1), HaarModel(22, 1.35, 2) ]#,  ]#, , , ] HaarModel(33, 1.65, 1)

while True:
    # Захват кадра
    ret, image = cap.read()
    #image = cv2.rotate(image, cv2.ROTATE_180)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


    #1 детектит более точно маленькие области глаз
    #2 детектит двойные рамки вокруг глаз
    frame_eyes = numpy.empty(shape=(0, 4), dtype=int)
    frame_eye_levels = numpy.empty(shape=(0,), dtype=int)
    for model in models:
        actual_min_size = int(model.min_size * model.scale_factor)
        new_eyes, _, new_eye_levels = eye_cascade.detectMultiScale3(gray,
                                                        scaleFactor=model.scale_factor, minNeighbors=model.neighbours,
                                                        minSize=(actual_min_size, actual_min_size),
                                                        outputRejectLevels=True)

        if type(new_eyes) is tuple:
            continue # Не нашли глаз

        try:
            frame_eyes = numpy.append(frame_eyes, new_eyes.astype(int), axis=0)
            frame_eye_levels = numpy.append(frame_eye_levels, new_eye_levels, axis=0)
        except:
            continue

    total_eyes = frame_eyes
    total_eye_levels = frame_eye_levels
    for eyes in previous_eyes:
        total_eyes = numpy.append(total_eyes, eyes, axis=0)
    for eye_levels in previous_eyes_levels:
        total_eye_levels = numpy.append(total_eye_levels, eye_levels, axis=0)

    if len(previous_eyes) == frames_count:
        previous_eyes.popleft()
        previous_eyes_levels.popleft()
    previous_eyes.append(frame_eyes)
    previous_eyes_levels.append(frame_eye_levels)

    zipped = [(*total_eyes[i], total_eye_levels[i]) for i in range(len(total_eyes))]

    merged_boxes = []
    for i, (ex, ey, ew, eh, confidence) in enumerate(zipped):
        merged = False
        for j, (mx, my, mw, mh, mconfidence) in enumerate(merged_boxes):
            # Проверяем, находится ли текущий box внутри уже слиянного box
            if ex >= mx and ey >= my and ex + ew <= mx + mw and ey + eh <= my + mh:
                # Текущий box находится внутри слиянного box, пропускаем его
                merged = True
                if i < frame_eyes.size:
                    merged_boxes[j] = (ex, ey, ew, eh, (confidence + mconfidence) * 6)
                else:
                    merged_boxes[j] = (mx, my, mw, mh, (confidence + mconfidence) * 3)
                break
            # Проверяем, находятся ли центры текущего и слиянного box достаточно близко друг к другу
            center = Point(ex + ew // 2, ey + eh // 2)
            mcenter = Point(mx + mw // 2, my + mh // 2)
            distance = center.calc_distance(mcenter)
            if distance < (ew + eh + mw + mh) / 5:
                # Центры достаточно близки, заменяем слиянным box со средними значениями
                if i < frame_eyes.size:
                    merged_boxes[j] = (
                    (ex + mx) // 2, (ey + my) // 2, (ew + mw) // 2, (eh + mh) // 2, (confidence + mconfidence) * 3)
                else:
                    if distance < (ew + eh + mw + mh) / frames_count * 3:
                        merged_boxes[j] = (
                            mx, my, mw, mh , (confidence + mconfidence) * 2)
                merged = True
                break
        if not merged:
            # Текущий box не слился с другими, добавляем его в список слияния
            merged_boxes.append((ex, ey, ew, eh, confidence))

    # Сортировка слиянных boxes
    sorted_boxes = sorted(merged_boxes, key=lambda i: i[4], reverse=True)

    # Отображение только половины самых надежных по количеству слияний boxes
    # half_length = len(sorted_boxes) // 2
    # half_length = max(half_length, 3)
    best_length = min(1, len(sorted_boxes))
    final_boxes = sorted_boxes[:best_length]
    # Отображение boxes на изображении
    for i, (ex, ey, ew, eh, confidence) in enumerate(final_boxes):
        cv2.rectangle(image, (ex, ey), (ex + ew, ey + eh),
                      (255 / len(final_boxes) * i, 255 / len(final_boxes) * i, 255), 2)

    # Отображение результата
    image = cv2.resize(image, (640, 480), interpolation=cv2.INTER_AREA)
    cv2.imshow("Pupil Detection", image)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Освобождение ресурсов
cap.release()
cv2.destroyAllWindows()