import cv2
import numpy as np

face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
eye_cascade = cv2.CascadeClassifier('haarcascade_eye.xml')


# Функция для проверки цвета внутри окружности
def is_dark_circle(img, center, radius):
    # Создание маски для выделения области внутри окружности
    mask = np.zeros_like(img[:, :, 0])
    cv2.circle(mask, center, radius, 255, -1)

    # Применение маски к исходному изображению
    roi = cv2.bitwise_and(img, img, mask=mask)

    # Вычисление среднего значения яркости внутри области
    mean_brightness = cv2.mean(roi, mask=mask)[0]

    # Если среднее значение яркости ниже порога, считаем окружность темной
    if mean_brightness < 87:
        return True
    else:
        return False

# Открытие видеопотока
cap = cv2.VideoCapture(1)

while True:
    # Захват кадра
    ret, frame = cap.read()

    # Преобразование в оттенки серого
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Применить каскад Хаара для обнаружения глаз

    blur = cv2.GaussianBlur(gray, (9, 9), 0)

    faces = face_cascade.detectMultiScale(gray, 1.1, 6, 0, (0, 0))
    if len(faces) == 0:

        eyes = eye_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=2)
        if len(eyes) == 0:
            circles = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, 1, 5,
                                       param1=30, param2=15, minRadius=5, maxRadius=20)

            # Если обнаружены окружности
            if circles is not None:
                # Обход по обнаруженным окружностям
                for i in circles[0, :]:
                    # Извлечение координат центра и радиуса
                    center = (int(i[0]), int(i[1]))
                    radius = int(i[2])

                    # Проверка, является ли окружность темной
                    if is_dark_circle(frame, center, radius):
                        # Рисование окружности на кадре
                        cv2.circle(frame, center, radius, (0, 255, 0), 2)

                        # Рисование центра окружности
                        cv2.circle(frame, center, 2, (0, 0, 255), 3)


        for (x, y, w, h) in eyes:
            cv2.rectangle(frame, (x, + y), (x + w, y + h), (255, 255, 255), 2)

            # Применение фильтра Гаусса для сглаживания
            cropped_eye = blur[y: y + h, x:x + w]

            # Обнаружение окружностей с помощью преобразования Хафа
            circles = cv2.HoughCircles(cropped_eye, cv2.HOUGH_GRADIENT, 1, 5,
                                       param1=30, param2=15, minRadius=5, maxRadius=20)

            # Если обнаружены окружности
            if circles is not None:
                # Обход по обнаруженным окружностям
                for i in circles[0, :]:
                    # Извлечение координат центра и радиуса
                    center = (int(i[0]) + x, int(i[1] + y))
                    radius = int(i[2])

                    # Проверка, является ли окружность темной
                    if is_dark_circle(frame, center, radius):
                        # Рисование окружности на кадре
                        cv2.circle(frame, center, radius, (0, 255, 0), 2)

                        # Рисование центра окружности
                        cv2.circle(frame, center, 2, (0, 0, 255), 3)


    # Для каждого обнаруженного лица
    for (fx, fy, fw, fh) in faces:
        # Выделяем область лица
        roi_gray = gray[fy:fy + fh, fx:fx + fw]
        roi_color = frame[fy:fy + fh, fx:fx + fw]

        # Отрисовываем прямоугольник вокруг лица
        cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (255, 0, 0), 2)
        eyes = eye_cascade.detectMultiScale(roi_gray, scaleFactor=1.1, minNeighbors=2)

        if len(eyes) == 0:
            circles = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, 1, 5,
                                       param1=30, param2=15, minRadius=5, maxRadius=20)

            # Если обнаружены окружности
            if circles is not None:
                # Обход по обнаруженным окружностям
                for i in circles[0, :]:
                    # Извлечение координат центра и радиуса
                    center = (int(i[0]), int(i[1]))
                    radius = int(i[2])

                    # Проверка, является ли окружность темной
                    if is_dark_circle(frame, center, radius):
                        # Рисование окружности на кадре
                        cv2.circle(frame, center, radius, (0, 255, 0), 2)

                        # Рисование центра окружности
                        cv2.circle(frame, center, 2, (0, 0, 255), 3)


        for (x, y, w, h) in eyes:
            cv2.rectangle(frame, (fx + x, fy + y), (fx + x + w, fy + y + h), (255, 255, 255), 2)

            # Применение фильтра Гаусса для сглаживания
            cropped_eye = blur[fy+y: fy+y+h, fx+x:fx+x+w]

            # Обнаружение окружностей с помощью преобразования Хафа
            circles = cv2.HoughCircles(cropped_eye, cv2.HOUGH_GRADIENT, 1, 5,
                                       param1=30, param2=15, minRadius=5, maxRadius=20)

            # Если обнаружены окружности
            if circles is not None:
                # Обход по обнаруженным окружностям
                for i in circles[0, :]:
                    # Извлечение координат центра и радиуса
                    center = (int(i[0]) + x, int(i[1] + y))
                    radius = int(i[2])

                    # Проверка, является ли окружность темной
                    if is_dark_circle(frame, center, radius):
                        # Рисование окружности на кадре
                        cv2.circle(frame, center, radius, (0, 255, 0), 2)

                        # Рисование центра окружности
                        cv2.circle(frame, center, 2, (0, 0, 255), 3)

    # Отображение обработанного кадра
    cv2.imshow('Pupil Detection', frame)

    # Выход из цикла по нажатию клавиши 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Освобождение ресурсов
cap.release()
cv2.destroyAllWindows()