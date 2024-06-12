from functools import partial

import numpy
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from tracker.protocol import BoundingBox
from tracker.ui.video_label import CallbacksVideoLabel


class MainWindow(QMainWindow):
    new_tracker = pyqtSignal(BoundingBox)
    rotate = pyqtSignal(int)

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
        self.rotate_actions = {}
        for i, angle in enumerate(self.angles):
            rotate = QAction(f'{angle}°', self)
            rotate.triggered.connect(partial(self.rotate.emit, self.angles[i]))
            rotate_image.addAction(rotate)
            self.rotate_actions[angle] = rotate

        calibrate_tracker = self.menu_bar.addMenu('Калибровка взгляда')

        start_calibrate = QAction('Начать', self)
        end_calibrate = QAction('Остановить', self)

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
