import time
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

REPO_ROOT = Path(__file__).resolve().parent.parent

# Сравниваем: Слева - v1 (оригинал), Справа - Ultimate (40 эпох)
PATH_L = REPO_ROOT / "yolo26n_pupil_best.pt"         # v1
PATH_R = REPO_ROOT / "yolo26n_finetuned_peak.pt"     # Ultimate
NAME_L = "YOLO26n v1"
NAME_R = "YOLO26n Ultimate (40 ep)"
COLOR_L = (0, 215, 255)  # Желтый
COLOR_R = (0, 255, 100)  # Зеленый

VIDEO_SOURCE = r"C:\Users\Admin\Videos\iVCam\20261017151527.mp4"
IMGSZ = 640
CONF_THRES = 0.01

print(f"Loading {NAME_L} and {NAME_R}...")
model_left = YOLO(str(PATH_L))
model_right = YOLO(str(PATH_R))

cap = cv2.VideoCapture(VIDEO_SOURCE)
if not cap.isOpened():
    print(f"Error: Could not open {VIDEO_SOURCE}")
    exit(1)

window_name = f"Compare: {NAME_L} vs {NAME_R}"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.resizeWindow(window_name, 1600, 520)

print(f"Playing: {VIDEO_SOURCE}")
print("Controls: SPACE = Pause, D / RIGHT ARROW = Step, Q / ESC = Exit")

paused = False


def process_frame(model, frame, title, color):
    t0 = time.perf_counter()
    results = model(frame, verbose=False, imgsz=IMGSZ)
    dt_ms = (time.perf_counter() - t0) * 1000.0

    annotated = frame.copy()
    boxes = results[0].boxes
    num_det = 0

    if boxes is not None:
        for box in boxes:
            conf = float(box.conf[0])
            if conf < CONF_THRES:
                continue
            num_det += 1
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            w, h = x2 - x1, y2 - y1
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)
            cv2.circle(annotated, (cx, cy), 5, (0, 0, 255), -1)
            cv2.circle(annotated, (cx, cy), 11, (255, 255, 255), 1)

            cv2.putText(
                annotated,
                f"{conf:.2f} | {w}x{h}",
                (x1, max(35, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                color,
                2,
                cv2.LINE_AA,
            )

    header = f"{title} | {dt_ms:.1f}ms | Det: {num_det}"
    cv2.putText(annotated, header, (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(annotated, header, (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)
    return annotated


prev_time = time.time()

while True:
    if not paused:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
            if not ret:
                break

    vis_l = process_frame(model_left, frame, NAME_L, COLOR_L)
    vis_r = process_frame(model_right, frame, NAME_R, COLOR_R)

    target_h = 540
    target_w = int(frame.shape[1] * (target_h / frame.shape[0]))
    l_res = cv2.resize(vis_l, (target_w, target_h))
    r_res = cv2.resize(vis_r, (target_w, target_h))

    divider = np.full((target_h, 4, 3), 255, dtype=np.uint8)
    combined = np.hstack([l_res, divider, r_res])

    curr_time = time.time()
    fps = 1.0 / max(1e-5, (curr_time - prev_time))
    prev_time = curr_time

    status = "PAUSED" if paused else f"FPS: {fps:.1f}"
    cv2.putText(
        combined,
        status,
        (combined.shape[1] // 2 - 50, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 255) if paused else (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.imshow(window_name, combined)

    key = cv2.waitKey(20 if not paused else 0) & 0xFF
    if key in (ord("q"), 27):
        break
    elif key == ord(" "):
        paused = not paused
    elif key in (ord("d"), 83):
        paused = True
        ret, frame = cap.read()

cap.release()
cv2.destroyAllWindows()
