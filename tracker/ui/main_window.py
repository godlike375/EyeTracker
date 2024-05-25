import numpy
from PyQt6.QtCore import pyqtSignal, QSize
from PyQt6.QtGui import QAction, QImage, QPixmap
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from tracker.overlays import ObjectsPainter
from tracker.protocol import BoundingBox
from tracker.ui.video_box import CallbacksLabel


class MainWindow(QMainWindow):
    new_tracker = pyqtSignal(BoundingBox)
    select_eye = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.video_label = CallbacksLabel(self)
        layout = QVBoxLayout()
        layout.addWidget(self.video_label)

        self.overlay = ObjectsPainter(self.video_label)
        self.overlay.setGeometry(self.video_label.geometry())
        self.overlay.show()

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

        self.video_size_set = False

    def update_video_frame(self, frame: numpy.ndarray):
        image = QImage(frame, frame.shape[1], frame.shape[0], QImage.Format.Format_BGR888)
        pixmap = QPixmap.fromImage(image)
        self.video_label.setPixmap(pixmap)

        if not self.video_size_set:
            self.video_label.setFixedSize(QSize(frame.shape[1], frame.shape[0]))
            self.video_size_set = True

    def keyPressEvent(self, event):
        self.video_label.keyPressEvent(event)
