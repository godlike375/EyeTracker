# import cv2
# import numpy as np
#
# # 1. Выбираем самый "грубый" словарь для низкого разрешения
# # 4x4 - это размер сетки внутри маркера, 50 - количество доступных ID
# aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
#
# # 2. Параметры сетки
# rows = 2          # Количество маркеров по вертикали
# cols = 2          # Количество маркеров по горизонтали
# marker_size = 200 # Размер одного маркера в пикселях (для печати)
# marker_sep = 50   # Расстояние между маркерами в пикселях
#
# # 3. Создаем объект доски (Grid Board)
# # В OpenCV 4.x это делается так:
# board = cv2.aruco.GridBoard((cols, rows), marker_size, marker_sep, aruco_dict)
#
# # 4. Генерируем изображение для печати
# # Размер изображения должен учитывать количество маркеров и отступы
# img_width = cols * marker_size + (cols - 1) * marker_sep + 100
# img_height = rows * marker_size + (rows - 1) * marker_sep + 100
#
# board_img = board.generateImage((img_width, img_height), marginSize=50)
#
# # 5. Сохраняем
# cv2.imwrite("aruco_monkey_board.png", board_img)
# print("Файл aruco_monkey_board.png создан. Готов к печати.")



import cv2
import numpy as np

# --- 1. ПАРАМЕТРЫ ИНИЦИАЛИЗАЦИИ ---
# Те же параметры, что мы использовали при генерации доски
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
marker_size = 0.05  # 2 см в метрах
marker_sep = 0.01   # 0.5 см в метрах
board = cv2.aruco.GridBoard((2, 2), marker_size, marker_sep, aruco_dict)
parameters = cv2.aruco.DetectorParameters()
parameters.adaptiveThreshConstant = 40
parameters.adaptiveThreshWinSizeMin = 10
parameters.adaptiveThreshWinSizeMax = 50
parameters.adaptiveThreshWinSizeStep = 10

# 2. Если маркеры очень маленькие в кадре:
parameters.minMarkerPerimeterRate = 0.08  # Искать даже крошечные объекты
parameters.maxMarkerPerimeterRate = 1.8
# 3. Самое важное: Усиление детекции битов
parameters.errorCorrectionRate = 3.0    # Позволяет игнорировать часть ошибочных битов
parameters.minDistanceToBorder = 1       # Если маркер почти у края кадра
detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
# --- 2. ЗАГЛУШКИ КАЛИБРОВКИ (ЗАМЕНИТЬ НА СВОИ!) ---
# Эти числа взяты "с потолка". Без реальной калибровки точность будет нулевой.
# f = 480 # Фокусное расстояние примерно равно ширине кадра
# cx, cy = 240, 426 # Оптический центр в середине
f = 1080
cx, cy = 540, 910
camera_matrix = np.array([[f, 0, cx],
                        [0, f, cy],
                        [0, 0, 1]], dtype=np.float32)
dist_coeffs = np.zeros((5, 1)) # Допускаем отсутствие дисторсии (временно)

# --- 3. ОТКРЫТИЕ ВИДЕОФАЙЛА ---
video_path = r"C:\Users\Admin\Downloads\20260112_140001.mp4" # Укажите путь к вашему файлу
cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print(f"Ошибка: Не удалось открыть файл {video_path}")
    exit()

print("Нажмите 'q' для выхода из просмотра.")

while cap.isOpened():
    ret, frame = cap.read()

    # Если кадры закончились - выходим из цикла
    if not ret:
        print("Видео завершено или произошла ошибка чтения.")
        break

    frame = cv2.resize(frame, (480, 800), interpolation=cv2.INTER_AREA)
    frame = cv2.flip(frame, 1)

    # --- 4. ДЕТЕКЦИЯ И ОБРАБОТКА ---
    corners, ids, rejected = detector.detectMarkers(frame)

    if ids is not None and len(ids) > 0:
        cv2.aruco.drawDetectedMarkers(frame, corners, ids)

        # Сопоставляем найденные углы с 3D моделью доски
        obj_points, img_points = board.matchImagePoints(corners, ids)
        if obj_points is None:
            cv2.imshow('Monkey Head Tracking', frame)
            key = cv2.waitKey(25) & 0xFF
            print('error')
            continue
#        frame = cv2.circle(frame, (int(corners[0][0][0][0]), int(corners[0][0][0][1])), 5, (255, 0, 0), 5)
        if len(obj_points) > 0:
            # Вычисляем позицию головы (PnP)
            success, rvec, tvec = cv2.solvePnP(obj_points, img_points, camera_matrix, dist_coeffs)

            if success:
                # Рисуем 3D оси на лбу макаки
                cv2.drawFrameAxes(frame, camera_matrix, dist_coeffs, rvec, tvec, 0.25)

                # Вывод координат (X, Y, Z) в метрах
                x, y, z = tvec.flatten()
                #cv2.putText(frame, f"XYZ: {x:.2f} {y:.2f} {z:.2f}m", (10, 30),
                #            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)

    # --- 5. ОТОБРАЖЕНИЕ ---
    cv2.imshow('Monkey Head Tracking', frame)

    # Выход по нажатию клавиши 'q' или 'Esc'
    key = cv2.waitKey(25) & 0xFF
    if key == ord('q') or key == 27:
        break

# Освобождаем ресурсы
cap.release()
cv2.destroyAllWindows()

# Примечание: camera_matrix и dist_coeffs нужно получить через cv2.calibrateCamera