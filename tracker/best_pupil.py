from threading import Thread

import cv2
import numpy
import numpy as np

from tracker.utils.fps import FPSCounter

cap = cv2.VideoCapture(1)
eye_cascade = cv2.CascadeClassifier('haarcascade_eye.xml')
fps = FPSCounter()

ret, image = cap.read()

def camera_get():
    global image
    while True:
        ret, image = cap.read()

cam_thread = Thread(target=camera_get, daemon=True)
cam_thread.start()

while True:
    fps.count_frame()
    if fps.able_to_calculate():
        print(fps.calculate())
    # Захват кадра

    contrast = 1.3  # коэффициент контрастности
    brightness = -60  # смещение яркости
    image = cv2.addWeighted(image, contrast, numpy.zeros(image.shape, image.dtype), 0, brightness)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(gray)

    # Рассчитываем пороговое значение для 1% самых тёмных пикселей
    threshold = (min_val + 1) * 3

    # Создаём маску для тёмных пикселей
    mask = gray <= threshold

    # Находим координаты пикселей в маске
    coords = np.where(mask)

    # Рисуем точки на изображении
    for i in range(len(coords[0])):
        cv2.circle(image, (coords[1][i], coords[0][i]), 2, (255, 0, 255), -1)

    # Использование каскадов Хаара для детектирования глаз
    eyes = eye_cascade.detectMultiScale(gray, scaleFactor=1.485, minNeighbors=1, minSize=(21, 21), maxSize=(270, 270))

    # Поиск зрачка внутри области глаз
    left_pupil = []
    right_pupil = []
    darkest_brightness = 255
    largest_area = 0

    for (ex, ey, ew, eh) in eyes:
        eye_region = gray[ey:ey + eh, ex:ex + ew]
        eye_thresholded = cv2.adaptiveThreshold(eye_region, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 3,
                                                0)
        eye_contours, _ = cv2.findContours(eye_thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in eye_contours:
            area = cv2.contourArea(contour)
            if area < 100:
                continue
            perimeter = cv2.arcLength(contour, True)
            if perimeter < 0.28:
                continue
            circularity = 4 * np.pi * area / (perimeter * perimeter)
            if circularity < 0.23:
                continue
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"]) + ex
                cy = int(M["m01"] / M["m00"]) + ey

                brightness = np.mean(eye_region)
                if brightness < darkest_brightness and area > largest_area:
                    darkest_brightness = brightness
                    largest_area = area

                    if cx < image.shape[1] // 2:
                        left_pupil = [(cx, cy)]
                    else:
                        right_pupil = [(cx, cy)]

    # Отображение найденных зрачков
    for pupil in left_pupil:
        cv2.circle(image, pupil, 3, (0, 255, 0), -1)
    for pupil in right_pupil:
        cv2.circle(image, pupil, 3, (0, 0, 255), -1)

    # Отображение результата
    cv2.imshow("Pupil Detection", image)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Освобождение ресурсов
cap.release()
cv2.destroyAllWindows()
