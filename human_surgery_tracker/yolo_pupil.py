import time
from pathlib import Path

import cv2
from ultralytics import YOLO

# Путь к обученной модели
REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = REPO_ROOT / "human_surgery_tracker" / "models" / "yolo26n_finetuned_peak_openvino_model"
if not MODEL_PATH.exists():
    MODEL_PATH = REPO_ROOT / "yolo26n_finetuned_peak.pt"
if not MODEL_PATH.exists():
    MODEL_PATH = REPO_ROOT / "yolo26n_pupil_best.pt"

IMGSZ = 640

# Инициализируем модель детекции
model = YOLO(str(MODEL_PATH))
video_source = r"C:\Users\Admin\Videos\iVCam\20261017151527.mp4"
cap = cv2.VideoCapture(video_source)

frame_count = 0
prev_time = time.time()
fps = 0.0
paused = False

window_name = "Pupil Detection Test (YOLOv8n)"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
# Устанавливаем комфортный размер окна на мониторе (можно менять мышкой)
cv2.resizeWindow(window_name, 960, 540)

print(f"Loaded model: {MODEL_PATH}")
print(f"Reading video: {video_source}")
print("Controls: 'q' or ESC to exit, SPACE to pause/resume.")

while True:
    if not paused:
        ret, frame = cap.read()
        if not ret:
            # Зацикливаем видео при окончании
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
            if not ret:
                break

        annotated = frame.copy()

        # Инференс детекции зрачка
        results = model(frame, verbose=False, imgsz=IMGSZ)
        boxes = results[0].boxes

        if boxes is not None:
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                label = model.names[cls]

                if conf < 0.01:
                    continue

                # Координата центра зрачка
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                # Рисуем bounding box и точку центра зрачка
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.circle(annotated, (cx, cy), 4, (0, 0, 255), -1)

                # Текст с уверенностью и координатами
                text = f"{label} {conf:.2f} ({cx}, {cy})"
                cv2.putText(annotated, text, (x1, max(25, y1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Подсчет и отображение FPS
        frame_count += 1
        curr_time = time.time()
        fps = 1.0 / max(1e-5, (curr_time - prev_time))
        prev_time = curr_time

        cv2.putText(annotated, f"FPS: {fps:.1f}", (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

    cv2.imshow(window_name, annotated)
    key = cv2.waitKey(20) & 0xFF
    if key in (ord('q'), 27):
        break
    elif key == ord(' '):
        paused = not paused

cap.release()
cv2.destroyAllWindows()
