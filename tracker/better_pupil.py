from threading import Thread

import cv2

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

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # Использование каскадов Хаара для детектирования глаз
    eyes = eye_cascade.detectMultiScale(gray, scaleFactor=1.52, minNeighbors=3, minSize=(22, 22), maxSize=(250, 250))

    # Поиск зрачка внутри области глаз
    left_pupil = []
    right_pupil = []
    darkest_brightness = 255
    largest_area = 0

    for (ex, ey, ew, eh) in eyes:
        cv2.rectangle(image, (ex, ey), (ex + ew, ey + eh), (255, 255, 255), 2)
        eye_region = gray[ey:ey + eh, ex:ex + ew]
        #cv2.circle(image, (ex+ew // 2, ey + eh // 2), 3, (255, 255, 0), -1)
        eye_thresholded = cv2.adaptiveThreshold(eye_region, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 85, -75)
        cv2.imshow('thresh', eye_thresholded)
        eye_contours, _ = cv2.findContours(eye_thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in eye_contours:
            area = cv2.contourArea(contour)
            #if area < 168:
            #    continue
            #perimeter = cv2.arcLength(contour, True)
            #if perimeter < 0.565:
            #    continue
            #circularity = 4 * np.pi * area / (perimeter * perimeter)
            #if circularity < 0.115:
            #    continue
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"]) + ex
                cy = int(M["m01"] / M["m00"]) + ey

                brightness = cv2.mean(eye_region)[0]
                area = cv2.contourArea(contour)

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
