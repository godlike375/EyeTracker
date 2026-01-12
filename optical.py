import sys
import cv2
import numpy as np
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QLabel, QVBoxLayout, QWidget, QPushButton
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage, QPixmap, QMouseEvent


class OpticalFlowTracker(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sparse Optical Flow Tracker")
        self.setGeometry(100, 100, 800, 600)

        self.video_path = None
        self.cap = None
        self.frame = None
        self.gray_prev = None
        self.points = []  # список точек [(x, y), ...]
        self.trajectories = []  # список траекторий: [[(x1,y1), (x2,y2), ...], ...]
        self.is_playing = False

        # настройки Lucas-Kanade
        self.lk_params = dict(
            winSize=(50, 50),
            maxLevel=4,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 40, 0.03)
        )

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()

        self.label = QLabel("Выберите видео")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        self.btn_open = QPushButton("Открыть видео")
        self.btn_open.clicked.connect(self.open_video)
        layout.addWidget(self.btn_open)

        self.btn_play = QPushButton("Запустить трекинг")
        self.btn_play.setEnabled(False)
        self.btn_play.clicked.connect(self.toggle_play)
        layout.addWidget(self.btn_play)

        central_widget.setLayout(layout)

    def open_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите видео", "", "Видео (*.mp4 *.avi *.mov *.mkv)"
        )
        if not path:
            return

        self.video_path = path
        self.cap = cv2.VideoCapture(self.video_path)
        ret, frame = self.cap.read()
        if not ret:
            self.label.setText("Не удалось прочитать видео")
            return

        self.frame = frame.copy()
        self.gray_prev = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self.points.clear()
        self.trajectories.clear()
        self.is_playing = False

        self.display_frame()
        self.btn_play.setEnabled(True)

    def mousePressEvent(self, event: QMouseEvent):
        if not self.frame is None and event.button() == Qt.LeftButton:
            # Конвертируем координаты QLabel (с учётом scaling)
            pos = self.label.mapFromGlobal(event.globalPos())
            x = int(pos.x() * self.frame.shape[1] / self.label.width())
            y = int(pos.y() * self.frame.shape[0] / self.label.height())

            # Добавляем точку
            self.points.append([x, y])
            self.trajectories.append([(x, y)])
            self.display_frame()

    def display_frame(self, frame_to_show=None):
        if frame_to_show is None:
            frame_disp = self.frame.copy()
        else:
            frame_disp = frame_to_show.copy()

        # Рисуем точки и траектории
        for traj, pt in zip(self.trajectories, self.points):
            # Точка
            cv2.circle(frame_disp, (int(pt[0]), int(pt[1])), 5, (0, 0, 255), -1)
            # Траектория
            for i in range(1, len(traj)):
                cv2.line(
                    frame_disp,
                    (int(traj[i - 1][0]), int(traj[i - 1][1])),
                    (int(traj[i][0]), int(traj[i][1])),
                    (255, 0, 0),
                    2,
                )

        # Конверт в QImage
        h, w, ch = frame_disp.shape
        bytes_per_line = ch * w
        q_img = QImage(frame_disp.data, w, h, bytes_per_line, QImage.Format_BGR888)
        pixmap = QPixmap.fromImage(q_img)
        self.label.setPixmap(pixmap.scaled(self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def toggle_play(self):
        if not self.cap:
            return

        if self.is_playing:
            self.is_playing = False
            self.btn_play.setText("Запустить трекинг")
        else:
            self.is_playing = True
            self.btn_play.setText("Остановить")
            # Перематываем на начало (если уже что-то проигрывали)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            # Сбрасываем кадр
            ret, self.frame = self.cap.read()
            if not ret:
                return

            self.gray_prev = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)
            # Сбрасываем траектории (оставляем только начальные точки)
            self.trajectories = [[(p[0], p[1])] for p in self.points]
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_frame)
            self.timer.start(30)  # ~30 FPS

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret or not self.is_playing:
            self.timer.stop()
            self.is_playing = False
            self.btn_play.setText("Запустить трекинг")
            return

        gray_curr = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        pts_prev = np.float32(self.points).reshape(-1, 1, 2)

        if len(self.points) > 0:
            # Прямой поток
            pts_next, status_fwd, err = cv2.calcOpticalFlowPyrLK(
                self.gray_prev, gray_curr, pts_prev, None, **self.lk_params
            )

            # Обратный поток (для проверки)
            pts_back, status_bwd, _ = cv2.calcOpticalFlowPyrLK(
                gray_curr, self.gray_prev, pts_next, None, **self.lk_params
            )

            # Forward-backward error
            fb_error = np.linalg.norm(pts_prev - pts_back, axis=2).flatten()
            err = err.flatten()

            # Фильтрация
            MIN_CONSISTENCY = 10
            MAX_ERR = 1000.0

            reliable = (
                    (status_fwd.ravel() == 1) &
                    (status_bwd.ravel() == 1) &
                    (fb_error < MIN_CONSISTENCY) &
                    (err < MAX_ERR)
            )

            # Обновляем траектории
            new_points = []
            new_trajectories = []
            for i, is_good in enumerate(reliable):
                if is_good:
                    x, y = pts_next[i].ravel()
                    self.trajectories[i].append((x, y))
                    new_points.append([x, y])
                    new_trajectories.append(self.trajectories[i])
                else:
                    # Точка потеряна — можно:
                    # - удалить её (как здесь),
                    # - или пометить как "lost" и попытаться восстановить позже
                    pass

            self.points = new_points
            self.trajectories = new_trajectories

            self.gray_prev = gray_curr.copy()
            self.frame = frame.copy()

        self.display_frame_with_quality(frame)


    def display_frame_with_quality(self, frame_to_show=None):
        if frame_to_show is None:
            frame_disp = self.frame.copy()
        else:
            frame_disp = frame_to_show.copy()

        # Рисуем траектории
        for traj in self.trajectories:
            for i in range(1, len(traj)):
                cv2.line(frame_disp,
                         (int(traj[i-1][0]), int(traj[i-1][1])),
                         (int(traj[i][0]), int(traj[i][1])),
                         (255, 0, 0), 2)

        # Рисуем точки (зелёные — надёжные, красные — потеряны)
        pts = np.array(self.points)
        if len(pts) > 0:
            for (x, y) in pts:
                cv2.circle(frame_disp, (int(x), int(y)), 5, (0, 255, 0), -1)  # зелёная
                cv2.circle(frame_disp, (int(x), int(y)), 2, (255, 255, 255), -1)

        # Конверт в QImage...
        h, w, ch = frame_disp.shape
        bytes_per_line = ch * w
        q_img = QImage(frame_disp.data, w, h, bytes_per_line, QImage.Format_BGR888)
        pixmap = QPixmap.fromImage(q_img)
        self.label.setPixmap(pixmap.scaled(self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def closeEvent(self, event):
        if self.cap:
            self.cap.release()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OpticalFlowTracker()
    window.show()
    sys.exit(app.exec())