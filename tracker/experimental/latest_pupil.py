import cv2
import numpy as np


def find_pupil(eye_image):
    # Преобразование изображения в оттенки серого
    gray = eye_image

    # Вычисление градиентов
    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    magnitude = np.sqrt(sobel_x**2 + sobel_y**2)

    # Нормализация градиентов
    magnitude = cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)

    # Бинаризация изображения градиентов
    ret, binary = cv2.threshold(magnitude, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Поиск контуров на бинарном изображении
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Поиск наибольшего контура (предположительно, зрачка)
    largest_contour = max(contours, key=cv2.contourArea)

    # Получение координат центра зрачка
    moments = cv2.moments(largest_contour)
    if moments['m00'] != 0:
        cx = int(moments['m10'] / moments['m00'])
        cy = int(moments['m01'] / moments['m00'])
    else:
        cx, cy = 0, 0

    return cx, cy


eye_cascade = cv2.CascadeClassifier('../haarcascade_eye.xml')
video_capture = cv2.VideoCapture(1)

while True:
    # Capture frame-by-frame
    ret, frame = video_capture.read()

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    blur = cv2.medianBlur(gray, 5)

    # Детекция круглых объектов (зрачка)
    circles = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, 1, 20,
                               param1=50, param2=30, minRadius=10, maxRadius=50)

    # Если круги найдены
    if circles is not None:
        # Получение координат и радиуса наиболее вероятного круга (зрачка)
        circles = np.uint16(np.around(circles))
        best_circle = circles[0, 0]
        center_x, center_y, radius = best_circle[0], best_circle[1], best_circle[2]

        # Рисование круга на изображении
        cv2.circle(frame, (center_x, center_y), radius, (0, 255, 0), 2)

        # Вывод изображения с обозначенным зрачком
        cv2.imshow('Eye with Pupil', frame)

    eyes = eye_cascade.detectMultiScale(gray, scaleFactor=1.52, minNeighbors=3, minSize=(22, 22), maxSize=(250, 250))
    for (ex,ey,ew,eh) in eyes:
        eye_gray = gray[ey:ey+eh,ex:ex+ew]
        eye_color = frame[ey:ey+eh,ex:ex+ew]
        cv2.rectangle(frame,(ex,ey),(ex+ew,ey+eh),(255,0,0),2)
        px,py = find_pupil(eye_gray)
        cv2.rectangle(eye_color,(px,py),(px+1,py+1),(255, 255, 255),2)

    # Display the resulting frame
    cv2.imshow('Video', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# When everything is done, release the capture
video_capture.release()
cv2.destroyAllWindows()