import sys
import cv2
import numpy as np
import time
import math

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QFormLayout, QComboBox, QSpinBox, QDoubleSpinBox, QPushButton,
    QLabel, QFileDialog, QMessageBox, QLineEdit, QHBoxLayout, QScrollArea
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QImage, QPixmap


class VideoThread(QThread):
    frame_signal = pyqtSignal(np.ndarray)

    def __init__(self, video_path, board, detector, camera_matrix, dist_coeffs,
                 resize_size=None, flip_code=None, axis_length=0.15, fps_limit=30):
        super().__init__()
        self.video_path = video_path
        self.board = board
        self.detector = detector
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs
        self.resize_size = resize_size
        self.flip_code = flip_code
        self.axis_length = axis_length
        self.fps_limit = fps_limit
        self.running = True

        # Генерация геометрии головы один раз при инициализации
        self.head_points, self.eyes_data = self.generate_head_model()

    def generate_head_model(self):
        """
        Генерирует облако точек головы и детальные координаты глаз.
        Масштаб увеличен в 3 раза.
        """
        points = []
        # Параметры головы (эллипсоид)
        head_center = np.array([0.0, 0.18, 0.24])
        radii = np.array([0.225, 0.33, 0.27])

        num_theta, num_phi = 40, 30
        for i in range(num_theta):
            theta = 2 * math.pi * i / num_theta
            for j in range(num_phi):
                phi = math.pi * j / num_phi
                x = head_center[0] + radii[0] * math.sin(phi) * math.cos(theta)
                y = head_center[1] + radii[1] * math.cos(phi)
                z = head_center[2] + radii[2] * math.sin(phi) * math.sin(theta)
                points.append([x, y, z])

        # Параметры глаз (в 3х масштабе)
        eye_x = 0.105  # Смещение глаз от центра вправо/влево
        eye_y = 0.18   # Смещение вниз от доски
        eye_z = 0.08   # Глубина центра глазного яблока внутри головы

        # Расстояние от центра яблока до зрачка (радиус глаза ~2.5-3 см * 3)
        eye_radius = 0.07

        eyes_data = {}
        for side in ['left', 'right']:
            sign = -1 if side == 'left' else 1

            # 1. Центр глазного яблока (глубокая точка)
            center = np.array([sign * eye_x, eye_y, eye_z])

            # 2. Центр зрачка (на поверхности, ближе к камере, т.е. меньше Z)
            # Зрачок находится на той же линии X и Y, но выдвинут вперед по Z
            pupil = np.array([sign * eye_x, eye_y, eye_z - eye_radius])

            # 3. Вектор взгляда (от центра через зрачок)
            gaze_dir = pupil - center
            # Удлиняем луч для визуализации (на 1.2 метра)
            gaze_end = center + (gaze_dir / np.linalg.norm(gaze_dir)) * 0.2

            eyes_data[side] = {
                'center': center,
                'pupil': pupil,
                'gaze_end': gaze_end
            }

        return np.array(points, dtype=np.float32), eyes_data

    def stop(self):
        self.running = False
        self.wait()

    def run(self):
        cap = cv2.VideoCapture(self.video_path)

        delay = 0.0
        if self.fps_limit and self.fps_limit > 0:
            delay = 1.0 / self.fps_limit

        while self.running and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if self.flip_code is not None:
                frame = cv2.flip(frame, self.flip_code)

            if self.resize_size:
                frame = cv2.resize(frame, self.resize_size)

            corners, ids, rejected = self.detector.detectMarkers(frame)

            if ids is not None and len(ids) > 0:
                # Отрисовка маркеров (опционально, можно убрать для чистоты)
                # cv2.aruco.drawDetectedMarkers(frame, corners, ids)

                ret_pose, rvec, tvec = cv2.aruco.estimatePoseBoard(
                    corners, ids, self.board, self.camera_matrix, self.dist_coeffs,
                    None, None, False
                )

                if ret_pose > 0:
                    # Отрисовка осей доски
                    cv2.drawFrameAxes(
                        frame, self.camera_matrix, self.dist_coeffs,
                        rvec, tvec, self.axis_length
                    )

                    # Отрисовка 3D головы и лучей
                    self.draw_face_and_gaze(frame, rvec, tvec)

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.frame_signal.emit(rgb_frame)

            if delay > 0:
                time.sleep(delay)

        cap.release()

    def draw_face_and_gaze(self, img, rvec, tvec):
        # --- 1. Подготовка слоев для прозрачности ---
        # Создаем черную маску того же размера, что и кадр
        mask = np.zeros_like(img, dtype=np.uint8)

        R, _ = cv2.Rodrigues(rvec)
        points_cam = np.dot(R, self.head_points.T) + tvec
        z_values = points_cam[2, :]

        img_points, _ = cv2.projectPoints(self.head_points, rvec, tvec, self.camera_matrix, self.dist_coeffs)
        img_points = img_points.reshape(-1, 2).astype(int)

        if len(z_values) > 0:
            min_z, max_z = np.min(z_values), np.max(z_values)
            range_z = max_z - min_z if max_z != min_z else 1.0

            # Сортируем: сначала рисуем дальние, потом ближние (чтобы ближние перекрывали дальние на маске)
            sorted_indices = np.argsort(z_values)[::-1]

            for i in sorted_indices:
                px, py = img_points[i]
                if 0 <= px < img.shape[1] and 0 <= py < img.shape[0]:
                    # Вычисляем "альфу" (яркость на маске):
                    # Ближе к камере (min_z) -> 255 (непрозрачный)
                    # Дальше от камеры (max_z) -> 0 (полностью прозрачный)
                    alpha_val = int(255 * (1.0 - (z_values[i] - min_z) / range_z))
                    alpha_val = max(0, min(255, alpha_val))

                    # Рисуем точку на маске белым цветом с интенсивностью alpha_val
                    # Цвет (alpha_val, alpha_val, alpha_val)
                    cv2.circle(mask, (px, py), 2, (alpha_val, alpha_val, alpha_val), -1)

            # --- 2. Смешивание маски с основным изображением ---
            # Превращаем маску в массив от 0.0 до 1.0
            alpha_map = mask.astype(float) / 255.0

            # Цвет точек головы (пусть будут чисто белыми)
            head_color = np.array([255, 255, 255], dtype=float)

            # Формула смешивания: Итог = (1 - Альфа) * Фон + Альфа * Цвет_Точки
            # Это делается быстро через NumPy для всего кадра сразу
            img[:] = ((1.0 - alpha_map) * img + alpha_map * head_color).astype(np.uint8)

        # --- 3. Отрисовка глаз и лучей (поверх прозрачной головы, непрозрачно) ---
        for side in ['left', 'right']:
            eye = self.eyes_data[side]
            pts_3d = np.array([eye['center'], eye['pupil'], eye['gaze_end']], dtype=np.float32)
            pts_2d, _ = cv2.projectPoints(pts_3d, rvec, tvec, self.camera_matrix, self.dist_coeffs)
            pts_2d = pts_2d.reshape(-1, 2).astype(int)

            p_center, p_pupil, p_gaze = tuple(pts_2d[0]), tuple(pts_2d[1]), tuple(pts_2d[2])

            # Луч и стрелка
            cv2.line(img, p_center, p_gaze, (0, 165, 255), 2, cv2.LINE_AA)
            cv2.arrowedLine(img, p_pupil, p_gaze, (0, 255, 255), 2, cv2.LINE_AA, tipLength=0.2)

            # Точки (жирные и непрозрачные)
            cv2.circle(img, p_center, 6, (0, 0, 255), -1) # Центр яблока - Красный
            cv2.circle(img, p_pupil, 6, (0, 255, 0), -1)  # Зрачок - Зеленый


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ArUco Board Generator & Monkey Head Tracker")
        self.resize(1280, 720)

        tabs = QTabWidget()
        tabs.addTab(self.create_generate_tab(), "Генерация доски")
        tabs.addTab(self.create_tracking_tab(), "Трекинг видео")
        self.setCentralWidget(tabs)

    def create_generate_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        form = QFormLayout()

        self.gen_dict = QComboBox()
        dicts = [
            "DICT_4X4_50", "DICT_4X4_100", "DICT_4X4_250", "DICT_4X4_1000",
            "DICT_5X5_50", "DICT_5X5_100", "DICT_5X5_250", "DICT_5X5_1000",
            "DICT_6X6_50", "DICT_6X6_100", "DICT_6X6_250", "DICT_6X6_1000",
            "DICT_ARUCO_ORIGINAL"
        ]
        self.gen_dict.addItems(dicts)
        self.gen_dict.setCurrentText("DICT_4X4_50")
        form.addRow("Словарь:", self.gen_dict)

        self.gen_rows = QSpinBox(); self.gen_rows.setRange(1, 20); self.gen_rows.setValue(2)
        form.addRow("Строк:", self.gen_rows)

        self.gen_cols = QSpinBox(); self.gen_cols.setRange(1, 20); self.gen_cols.setValue(2)
        form.addRow("Столбцов:", self.gen_cols)

        self.gen_marker_px = QSpinBox(); self.gen_marker_px.setRange(50, 2000); self.gen_marker_px.setValue(200)
        form.addRow("Размер маркера (px):", self.gen_marker_px)

        self.gen_sep_px = QSpinBox(); self.gen_sep_px.setRange(0, 500); self.gen_sep_px.setValue(50)
        form.addRow("Отступ между маркерами (px):", self.gen_sep_px)

        self.gen_border_px = QSpinBox(); self.gen_border_px.setRange(0, 500); self.gen_border_px.setValue(50)
        form.addRow("Отступ по краям (px):", self.gen_border_px)

        layout.addLayout(form)

        btn_generate = QPushButton("Сгенерировать и сохранить изображение доски")
        btn_generate.clicked.connect(self.generate_board)
        layout.addWidget(btn_generate)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def generate_board(self):
        dict_name = self.gen_dict.currentText()
        dict_id = getattr(cv2.aruco, dict_name)
        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)

        cols = self.gen_cols.value()
        rows = self.gen_rows.value()
        marker_size = self.gen_marker_px.value()
        marker_sep = self.gen_sep_px.value()
        margin_size = self.gen_border_px.value()

        board = cv2.aruco.GridBoard(
            (cols, rows),
            marker_size,
            marker_sep,
            aruco_dict
        )

        img_width = cols * marker_size + (cols - 1) * marker_sep + 2 * margin_size
        img_height = rows * marker_size + (rows - 1) * marker_sep + 2 * margin_size

        board_img = board.generateImage((img_width, img_height), marginSize=margin_size)

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить доску", "aruco_board.png", "PNG (*.png);;Все файлы (*)"
        )
        if file_path:
            cv2.imwrite(file_path, board_img)
            QMessageBox.information(self, "Готово", f"Доска сохранена:\n{file_path}")

    def create_tracking_tab(self):
        widget = QWidget()
        main_layout = QVBoxLayout(widget)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        form = QFormLayout()

        # Ограничение FPS
        self.fps_limit = QSpinBox()
        self.fps_limit.setRange(0, 120)
        self.fps_limit.setValue(30)
        self.fps_limit.setSpecialValueText("Без ограничения")
        form.addRow("Ограничение FPS:", self.fps_limit)

        # Параметры детекции
        self.adaptiveThreshConstant = QSpinBox()
        self.adaptiveThreshConstant.setRange(1, 255)
        self.adaptiveThreshConstant.setValue(40)
        form.addRow("Adaptive Thresh Constant:", self.adaptiveThreshConstant)

        self.adaptiveThreshWinSizeMin = QSpinBox()
        self.adaptiveThreshWinSizeMin.setRange(5, 50)
        self.adaptiveThreshWinSizeMin.setSingleStep(5)
        self.adaptiveThreshWinSizeMin.setValue(5)
        form.addRow("WinSize Min:", self.adaptiveThreshWinSizeMin)

        self.adaptiveThreshWinSizeMax = QSpinBox()
        self.adaptiveThreshWinSizeMax.setRange(5, 100)
        self.adaptiveThreshWinSizeMax.setSingleStep(5)
        self.adaptiveThreshWinSizeMax.setValue(45)
        form.addRow("WinSize Max:", self.adaptiveThreshWinSizeMax)

        self.adaptiveThreshWinSizeStep = QSpinBox()
        self.adaptiveThreshWinSizeStep.setRange(5, 50)
        self.adaptiveThreshWinSizeStep.setValue(5)
        form.addRow("WinSize Step:", self.adaptiveThreshWinSizeStep)

        self.minMarkerPerimeterRate = QDoubleSpinBox()
        self.minMarkerPerimeterRate.setRange(0.01, 1.0)
        self.minMarkerPerimeterRate.setSingleStep(0.01)
        self.minMarkerPerimeterRate.setValue(0.04)
        form.addRow("Min Perimeter Rate:", self.minMarkerPerimeterRate)

        self.maxMarkerPerimeterRate = QDoubleSpinBox()
        self.maxMarkerPerimeterRate.setRange(1.0, 10.0)
        self.maxMarkerPerimeterRate.setSingleStep(0.1)
        self.maxMarkerPerimeterRate.setValue(1.8)
        form.addRow("Max Perimeter Rate:", self.maxMarkerPerimeterRate)

        self.errorCorrectionRate = QDoubleSpinBox()
        self.errorCorrectionRate.setRange(0.0, 10.0)
        self.errorCorrectionRate.setSingleStep(0.05)
        self.errorCorrectionRate.setValue(1.65)
        form.addRow("Error Correction Rate:", self.errorCorrectionRate)

        # Основные параметры доски
        self.track_dict = QComboBox()
        self.track_dict.addItems([
            "DICT_4X4_50", "DICT_4X4_100", "DICT_4X4_250", "DICT_4X4_1000",
            "DICT_5X5_50", "DICT_5X5_100", "DICT_5X5_250", "DICT_5X5_1000",
            "DICT_6X6_50", "DICT_6X6_100", "DICT_6X6_250", "DICT_6X6_1000",
            "DICT_ARUCO_ORIGINAL"
        ])
        self.track_dict.setCurrentText("DICT_4X4_50")
        form.addRow("Словарь:", self.track_dict)

        self.track_rows = QSpinBox(); self.track_rows.setRange(1, 20); self.track_rows.setValue(2)
        form.addRow("Строк:", self.track_rows)

        self.track_cols = QSpinBox(); self.track_cols.setRange(1, 20); self.track_cols.setValue(2)
        form.addRow("Столбцов:", self.track_cols)

        self.marker_m = QDoubleSpinBox(); self.marker_m.setRange(0.01, 1.0); self.marker_m.setSingleStep(0.001); self.marker_m.setValue(0.05)
        form.addRow("Размер маркера (м):", self.marker_m)

        self.sep_m = QDoubleSpinBox(); self.sep_m.setRange(0.0, 0.5); self.sep_m.setSingleStep(0.001); self.sep_m.setValue(0.01)
        form.addRow("Отступ между маркерами (м):", self.sep_m)

        # Калибровка камеры
        self.fx = QDoubleSpinBox(); self.fx.setRange(100, 10000); self.fx.setValue(1080)
        form.addRow("fx:", self.fx)

        self.fy = QDoubleSpinBox(); self.fy.setRange(100, 10000); self.fy.setValue(1080)
        form.addRow("fy:", self.fy)

        self.cx = QDoubleSpinBox(); self.cx.setRange(0, 5000); self.cx.setValue(540)
        form.addRow("cx:", self.cx)

        self.cy = QDoubleSpinBox(); self.cy.setRange(0, 5000); self.cy.setValue(910)
        form.addRow("cy:", self.cy)

        # Размер кадра
        self.resize_w = QSpinBox(); self.resize_w.setRange(0, 3840); self.resize_w.setValue(480)
        form.addRow("Ширина кадра (0 = оригинал):", self.resize_w)

        self.resize_h = QSpinBox(); self.resize_h.setRange(0, 2160); self.resize_h.setValue(800)
        form.addRow("Высота кадра:", self.resize_h)

        scroll_layout.addLayout(form)

        # Выбор видео
        video_hbox = QHBoxLayout()
        self.video_path = QLineEdit()
        self.video_path.setPlaceholderText("Путь к видео файлу")
        video_hbox.addWidget(self.video_path)
        browse_btn = QPushButton("Выбрать видео")
        browse_btn.clicked.connect(self.select_video)
        video_hbox.addWidget(browse_btn)
        scroll_layout.addLayout(video_hbox)

        # Кнопки управления
        btn_hbox = QHBoxLayout()
        self.start_btn = QPushButton("Запустить трекинг")
        self.start_btn.clicked.connect(self.start_tracking)
        btn_hbox.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Остановить")
        self.stop_btn.clicked.connect(self.stop_tracking)
        self.stop_btn.setEnabled(False)
        btn_hbox.addWidget(self.stop_btn)

        scroll_layout.addLayout(btn_hbox)
        scroll_layout.addStretch()


        # Видео (основная часть окна)
        self.video_label = QLabel("Видео появится здесь после запуска")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: black; border: 1px solid gray;")
        self.video_label.setMinimumHeight(640)
        scroll_layout.addWidget(self.video_label, stretch=1)


        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area, stretch=0)

        self.thread = None
        return widget

    def select_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать видео", "", "Видео (*.mp4 *.avi *.mov *.mkv)"
        )
        if path:
            self.video_path.setText(path)

            # Считываем параметры видео для установки дефолтной калибровки
            cap = cv2.VideoCapture(path)
            if cap.isOpened():
                w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                cap.release()

                if w > 0 and h > 0:
                    # Устанавливаем центр изображения
                    self.cx.setValue(w / 2)
                    self.cy.setValue(h / 2)
                    # Устанавливаем фокусное расстояние (аппроксимация: fx = fy = width)
                    self.fx.setValue(w)
                    self.fy.setValue(w)

                    # Сбрасываем ресайз в 0 (оригинал), чтобы параметры калибровки
                    # соответствовали размеру кадра при обработке
                    self.resize_w.setValue(0)
                    self.resize_h.setValue(0)

    def start_tracking(self):
        video_file = self.video_path.text()
        if not video_file:
            QMessageBox.warning(self, "Ошибка", "Сначала выберите видео")
            return

        dict_name = self.track_dict.currentText()
        dict_id = getattr(cv2.aruco, dict_name)
        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)

        board = cv2.aruco.GridBoard(
            (self.track_cols.value(), self.track_rows.value()),
            float(self.marker_m.value()),
            float(self.sep_m.value()),
            aruco_dict
        )

        params = cv2.aruco.DetectorParameters()
        params.adaptiveThreshConstant = self.adaptiveThreshConstant.value()
        params.adaptiveThreshWinSizeMin = self.adaptiveThreshWinSizeMin.value()
        params.adaptiveThreshWinSizeMax = self.adaptiveThreshWinSizeMax.value()
        params.adaptiveThreshWinSizeStep = self.adaptiveThreshWinSizeStep.value()
        params.minMarkerPerimeterRate = self.minMarkerPerimeterRate.value()
        params.maxMarkerPerimeterRate = self.maxMarkerPerimeterRate.value()
        params.errorCorrectionRate = self.errorCorrectionRate.value()

        detector = cv2.aruco.ArucoDetector(aruco_dict, params)

        camera_matrix = np.array([
            [self.fx.value(), 0, self.cx.value()],
            [0, self.fy.value(), self.cy.value()],
            [0, 0, 1]
        ], dtype=np.float32)

        dist_coeffs = np.zeros((5, 1))

        resize = None
        if self.resize_w.value() > 0 and self.resize_h.value() > 0:
            resize = (self.resize_w.value(), self.resize_h.value())

        flip_code = None

        fps_val = self.fps_limit.value()
        fps_limit = fps_val if fps_val > 0 else None

        self.thread = VideoThread(
            video_file, board, detector, camera_matrix, dist_coeffs,
            resize_size=resize, flip_code=flip_code, axis_length=0.15,
            fps_limit=fps_limit
        )
        self.thread.frame_signal.connect(self.update_frame)
        self.thread.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def stop_tracking(self):
        if self.thread:
            self.thread.stop()
            self.thread = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.video_label.clear()
        self.video_label.setText("Видео остановлено")

    def update_frame(self, cv_img):
        h, w, ch = cv_img.shape
        bytes_per_line = ch * w
        q_img = QImage(cv_img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)

        scaled_pixmap = pixmap.scaled(
            self.video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.video_label.setPixmap(scaled_pixmap)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())