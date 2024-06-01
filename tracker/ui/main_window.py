import numpy
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from tracker.protocol import BoundingBox
from tracker.ui.video_label import CallbacksVideoLabel


class MainWindow(QMainWindow):
    new_tracker = pyqtSignal(BoundingBox)
    select_eye = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.video_label = CallbacksVideoLabel(parent=self)
        layout = QVBoxLayout()
        layout.addWidget(self.video_label)

        # self.overlay = ObjectsPainter(self.video_label)
        # self.overlay.setGeometry(self.video_label.geometry())
        # self.overlay.show()

        self.menu_bar = self.menuBar()

        select_pupil = self.menu_bar.addMenu('Выделение глаза')
        start_select = QAction('Начать', self)
        start_select.triggered.connect(self.select_eye)
        end_select = QAction('Остановить', self)

        calibrate_tracker = self.menu_bar.addMenu('Калибровка взгляда')

        start_calibrate = QAction('Начать', self)
        #start.triggered.connect()
        end_calibrate = QAction('Остановить', self)

        # Добавление действий в меню
        select_pupil.addAction(start_select)
        select_pupil.addAction(end_select)
        calibrate_tracker.addAction(start_calibrate)
        calibrate_tracker.addAction(end_calibrate)

        # Добавление layout в основное окно
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        main_widget.setLayout(layout)

    def update_video_frame(self, frame: numpy.ndarray):
        self.video_label.set_frame(frame)

    def keyPressEvent(self, event):
        self.video_label.keyPressEvent(event)
