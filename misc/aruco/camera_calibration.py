import sys
import cv2
import numpy as np
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton,
    QVBoxLayout, QWidget, QMessageBox, QHBoxLayout,
    QFileDialog, QDialog, QDoubleSpinBox, QSpinBox, QFormLayout, QComboBox
)
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QTimer, Qt

# Доступные словари ArUco
ARUCO_DICTS = {
    "4x4_50": cv2.aruco.DICT_4X4_50,
    "4x4_250": cv2.aruco.DICT_4X4_250,
    "5x5_250": cv2.aruco.DICT_5X5_250,
    "6x6_250": cv2.aruco.DICT_6X6_250,
    "7x7_250": cv2.aruco.DICT_7X7_250,
}

class BoardConfig:
    """Объект для хранения текущих настроек доски"""
    def __init__(self):
        self.dict_key = "4x4_50"
        self.squares_x = 5
        self.squares_y = 7
        self.square_len = 0.04   # метры
        self.marker_len = 0.02   # метры

    def get_dict(self):
        return cv2.aruco.getPredefinedDictionary(ARUCO_DICTS[self.dict_key])

    def create_board(self):
        return cv2.aruco.CharucoBoard(
            (self.squares_x, self.squares_y),
            self.square_len,
            self.marker_len,
            self.get_dict()
        )

class BoardSettingsDialog(QDialog):
    """Окно детальной настройки параметров доски"""
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Настройка CharUco")
        layout = QFormLayout(self)

        self.combo_dict = QComboBox()
        self.combo_dict.addItems(ARUCO_DICTS.keys())
        self.combo_dict.setCurrentText(config.dict_key)

        self.spin_x = QSpinBox()
        self.spin_x.setRange(3, 20)
        self.spin_x.setValue(config.squares_x)

        self.spin_y = QSpinBox()
        self.spin_y.setRange(3, 20)
        self.spin_y.setValue(config.squares_y)

        self.spin_sq = QDoubleSpinBox()
        self.spin_sq.setRange(0.001, 1.0)
        self.spin_sq.setSingleStep(0.001)
        self.spin_sq.setDecimals(3)
        self.spin_sq.setValue(config.square_len)
        self.spin_sq.setSuffix(" m")

        self.spin_mk = QDoubleSpinBox()
        self.spin_mk.setRange(0.001, 1.0)
        self.spin_mk.setSingleStep(0.001)
        self.spin_mk.setDecimals(3)
        self.spin_mk.setValue(config.marker_len)
        self.spin_mk.setSuffix(" m")

        self.gen_btn = QPushButton("💾 Применить и сохранить PNG")
        self.gen_btn.clicked.connect(self.save_and_generate)

        layout.addRow("Словарь:", self.combo_dict)
        layout.addRow("Клеток по X:", self.spin_x)
        layout.addRow("Клеток по Y:", self.spin_y)
        layout.addRow("Размер клетки:", self.spin_sq)
        layout.addRow("Размер маркера:", self.spin_mk)
        layout.addWidget(self.gen_btn)

    def save_and_generate(self):
        # Обновляем конфиг
        self.config.dict_key = self.combo_dict.currentText()
        self.config.squares_x = self.spin_x.value()
        self.config.squares_y = self.spin_y.value()
        self.config.square_len = self.spin_sq.value()
        self.config.marker_len = self.spin_mk.value()

        if self.config.marker_len >= self.config.square_len:
            QMessageBox.warning(self, "Ошибка", "Маркер должен быть меньше клетки!")
            return

        board = self.config.create_board()
        # Рендерим для печати
        img = board.generateImage((2000, 2800))
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить PNG", "charuco_board.png", "Images (*.png)")
        if file_path:
            cv2.imwrite(file_path, img)
            QMessageBox.information(self, "Успех", "Параметры обновлены, файл сохранен.")
            self.accept()

class CameraCalibrator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = BoardConfig()
        self.obj_points = []
        self.img_points = []
        self.camera_matrix = None
        self.dist_coeffs = None
        self.calibration_done = False

        self.init_ui()
        self.init_camera()
        self.update_detector()

    def init_ui(self):
        self.setWindowTitle("Advanced CharUco Calibrator")
        self.setGeometry(100, 100, 1000, 750)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.video_label = QLabel("Ожидание видео...")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: #222; border-radius: 5px;")
        layout.addWidget(self.video_label)

        btn_box = QHBoxLayout()
        self.btn_cfg = QPushButton("⚙️ Настроить доску")
        self.btn_cap = QPushButton("📸 Снимок")
        self.btn_dir = QPushButton("📂 Из папки")
        self.btn_run = QPushButton("🎯 Калибровать")
        self.btn_save = QPushButton("💾 Сохранить .NPZ")

        for b in [self.btn_cfg, self.btn_cap, self.btn_dir, self.btn_run, self.btn_save]:
            btn_box.addWidget(b)

        layout.addLayout(btn_box)

        self.btn_cfg.clicked.connect(self.open_settings)
        self.btn_cap.clicked.connect(self.capture_frame)
        self.btn_dir.clicked.connect(self.load_from_folder)
        self.btn_run.clicked.connect(self.calibrate_camera)
        self.btn_save.clicked.connect(self.save_params)

    def update_detector(self):
        """Пересоздает детектор при изменении настроек доски"""
        self.board = self.config.create_board()
        self.detector = cv2.aruco.CharucoDetector(self.board)

    def open_settings(self):
        dialog = BoardSettingsDialog(self.config, self)
        if dialog.exec():
            self.update_detector()
            self.obj_points = [] # Сбрасываем старые точки, так как доска изменилась
            self.img_points = []
            QMessageBox.information(self, "Инфо", "Параметры доски изменены. Старые снимки удалены из памяти.")

    def init_camera(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret: return

        if self.calibration_done:
            h, w = frame.shape[:2]
            new_mtx, _ = cv2.getOptimalNewCameraMatrix(self.camera_matrix, self.dist_coeffs, (w,h), 1, (w,h))
            display_frame = cv2.undistort(frame, self.camera_matrix, self.dist_coeffs, None, new_mtx)
        else:
            display_frame = frame.copy()

        # Детекция
        c_corners, c_ids, m_corners, m_ids = self.detector.detectBoard(frame)
        if m_ids is not None:
            cv2.aruco.drawDetectedMarkers(display_frame, m_corners, m_ids)
        if c_ids is not None:
            cv2.aruco.drawDetectedCornersCharuco(display_frame, c_corners, c_ids, (0, 255, 0))

        # Отрисовка в GUI
        rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        q_img = QImage(rgb.data, w, h, ch*w, QImage.Format.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(q_img).scaled(
            self.video_label.width(), self.video_label.height(), Qt.AspectRatioMode.KeepAspectRatio))

    def capture_frame(self):
        ret, frame = self.cap.read()
        if not ret: return

        c_corners, c_ids, _, _ = self.detector.detectBoard(frame)
        if c_ids is not None and len(c_ids) > 4:
            objp, imgp = self.board.matchImagePoints(c_corners, c_ids)
            self.obj_points.append(objp)
            self.img_points.append(imgp)

            if not os.path.exists("captured"): os.makedirs("captured")
            cv2.imwrite(f"captured/frame_{len(self.obj_points)}.png", frame)
            QMessageBox.information(self, "📸", f"Записано снимков: {len(self.obj_points)}")
        else:
            QMessageBox.warning(self, "!", "Доска не видна или слишком мало углов")

    def load_from_folder(self):
        files = QFileDialog.getOpenFileNames(self, "Выбор", "", "Images (*.png *.jpg)")[0]
        count = 0
        for f in files:
            img = cv2.imread(f)
            c_corners, c_ids, _, _ = self.detector.detectBoard(img)
            if c_ids is not None:
                objp, imgp = self.board.matchImagePoints(c_corners, c_ids)
                self.obj_points.append(objp)
                self.img_points.append(imgp)
                count += 1
        QMessageBox.information(self, "📂", f"Добавлено {count} изображений")

    def calibrate_camera(self):
        if len(self.obj_points) < 5:
            QMessageBox.warning(self, "!", "Мало данных (нужно минимум 5 кадров)")
            return

        ret, frame = self.cap.read()
        h, w = frame.shape[:2]
        err, self.camera_matrix, self.dist_coeffs, _, _ = cv2.calibrateCamera(
            self.obj_points, self.img_points, (w, h), None, None
        )
        if err:
            self.calibration_done = True
            QMessageBox.information(self, "🎯", f"Ошибка: {err:.4f}\nКалибровка активна в реальном времени.")

    def save_params(self):
        if not self.calibration_done: return
        np.savez("calib_data.npz", mtx=self.camera_matrix, dist=self.dist_coeffs)
        QMessageBox.information(self, "💾", "Данные сохранены в calib_data.npz")

    def closeEvent(self, event):
        self.cap.release()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CameraCalibrator()
    window.show()
    sys.exit(app.exec())