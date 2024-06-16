from functools import partial

import numpy
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from tracker.protocol import BoundingBox
from tracker.ui.video_label import CallbacksVideoLabel


class MainWindow(QMainWindow):
    new_tracker = pyqtSignal(BoundingBox)
    rotate = pyqtSignal(int)
    start_calibration = pyqtSignal()
    stop_calibration = pyqtSignal()


    def __init__(self):
        super().__init__()
        self.video_label = CallbacksVideoLabel(parent=self)
        layout = QVBoxLayout()
        layout.addWidget(self.video_label)
        self.angles = [0, 90, 180, 270]

        # self.overlay = ObjectsPainter(self.video_label)
        # self.overlay.setGeometry(self.video_label.geometry())
        # self.overlay.show()

        self.menu_bar = self.menuBar()

        rotate_image = self.menu_bar.addMenu('Поворот изображения')
        for i, angle in enumerate(self.angles):
            rotate = QAction(f'{angle}°', self)
            rotate.triggered.connect(partial(self.rotate.emit, self.angles[i]))
            rotate_image.addAction(rotate)

        calibrate_tracker = self.menu_bar.addMenu('Калибровка взгляда')

        start_calibrate = QAction('Начать', self)
        start_calibrate.triggered.connect(self.start_calibration)
        end_calibrate = QAction('Остановить', self)
        end_calibrate.triggered.connect(self.stop_calibration)

        calibrate_tracker.addAction(start_calibrate)
        calibrate_tracker.addAction(end_calibrate)

        # Добавление layout в основное окно
        self.main_widget = QWidget(self)
        self.main_widget.setLayout(layout)
        self.setCentralWidget(self.main_widget)

    def adjust(self):
        self.main_widget.adjustSize()
        self.adjustSize()

    def update_video_frame(self, frame: numpy.ndarray):
        self.video_label.set_frame(frame)

    def keyPressEvent(self, event):
        self.video_label.keyPressEvent(event)
