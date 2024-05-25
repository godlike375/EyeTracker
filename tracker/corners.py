
import cv2

cap = cv2.VideoCapture(1)

while True:
    # Загрузить изображение
    ret, img = cap.read()

    # Преобразовать изображение в  grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Найти лучшие "угловые" точки
    corners = cv2.goodFeaturesToTrack(gray,
                                      maxCorners=1000,
                                      qualityLevel=0.001,
                                      minDistance=1)

    # Отобразить найденные точки
    for corner in corners:
        x, y = corner[0]
        cv2.circle(img, (int(x), int(y)), 5, (0, 0, 255), -1)

    # Показать результат
    cv2.imshow('Corners', img)
    cv2.waitKey(1)

cv2.destroyAllWindows()