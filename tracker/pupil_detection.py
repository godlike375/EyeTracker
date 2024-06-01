import cv2
import numpy as np

cap = cv2.VideoCapture(r'C:\Users\godlike\Desktop\Видео_макаки\снизу_близко.mp4')
eye_cascade = cv2.CascadeClassifier('haarcascade_eye.xml')

while True:
    # Захват кадра
    ret, image = cap.read()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # Использование каскадов Хаара для детектирования глаз

    eyes = eye_cascade.detectMultiScale(gray, scaleFactor=1.52, minNeighbors=2, minSize=(6, 6), maxSize=(250, 250))

    #eyes = eye_cascade.detectMultiScale(gray, scaleFactor=1.52, minNeighbors=3, minSize=(22, 22), maxSize=(250, 250))
    # Поиск зрачка внутри области глаз
    for (ex, ey, ew, eh) in eyes:
        cv2.rectangle(image, (ex, ey), (ex + ew, ey + eh), (255, 255, 255), 2)
        eye_region = gray[ey:ey + eh, ex:ex + ew]
        cv2.circle(image, (ex+ew // 2, ey + eh // 2), 3, (255, 255, 0), -1)
        eye_thresholded = cv2.adaptiveThreshold(eye_region, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 197, -5)
        eye_contours, _ = cv2.findContours(eye_thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in eye_contours:

            area = cv2.contourArea(contour)
            if area < 168:
                continue
            perimeter = cv2.arcLength(contour, True)
            if perimeter < 0.565:
                continue
            circularity = 4 * np.pi * area / (perimeter * perimeter)
            if circularity < 0.115:  # Пример значения порога для фильтрации по форме
                continue
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"]) + ex
                cy = int(M["m01"] / M["m00"]) + ey
                cv2.circle(image, (cx, cy), 3, (0, 0, 255), -1)

    # Отображение результата
    image = cv2.resize(image, (640, 480), interpolation=cv2.INTER_AREA)

    cv2.imshow("Pupil Detection", image)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Освобождение ресурсов
cap.release()
cv2.destroyAllWindows()