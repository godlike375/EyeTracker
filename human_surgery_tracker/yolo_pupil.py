import cv2
from ultralytics import YOLO

model = YOLO(r"C:\Users\Admin\Documents\GitHub\Eye-pupil-segmentation\runs\segment\train\weights\best.pt")
#YOLO(r"C:\Users\Admin\Downloads\yolo26m.pt")
cap = cv2.VideoCapture(r"C:\Users\Admin\Videos\iVCam\20261014134127.mp4")

skip_frames = 1  # обрабатывать каждый 5-й кадр
frame_count = 0

while True:
    ret, frame = cap.read()
    frame = cv2.resize(frame, (640, 480))  # например
    if not ret:
        break

    if frame_count % skip_frames == 0:
        results = model(frame, verbose=False, imgsz=190)
        # Извлекаем результаты
        boxes = results[0].boxes  # объект Boxes

        # Копируем кадр, чтобы не изменять оригинал напрямую (опционально)
        annotated = frame.copy()

        # Проходим по всем детекциям
        for box in boxes:
            # Получаем координаты [x1, y1, x2, y2]
            x1, y1, x2, y2 = map(int, box.xyxy[0])  # преобразуем в int для OpenCV
            conf = float(box.conf[0])               # уверенность
            cls = int(box.cls[0])                   # индекс класса
            label = model.names[cls]                # имя класса

            # Опционально: фильтрация по confidence
            if conf < 0.45:  # порог уверенности
                continue

            # Рисуем прямоугольник
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Добавляем текст с меткой и уверенностью
            text = f"{label} {conf:.2f}"
            cv2.putText(annotated, text, (x1, y1 + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    # Иначе используем предыдущий annotated_frame (или просто показываем оригинальный кадр)

    cv2.imshow("Fast YOLO", annotated if frame_count % skip_frames == 0 else frame)
    if cv2.waitKey(32) & 0xFF in (ord('q'), 27):
        break

    frame_count += 1

cap.release()
cv2.destroyAllWindows()