
from PyQt6.QtCore import Qt, QPoint, pyqtSlot
from PyQt6.QtCore import QTimerEvent
from PyQt6.QtWidgets import QMainWindow, QApplication, QPushButton

from tracker.utils.fps import FPS_120, MSEC_IN_SEC
from tracker.utils.shared_objects import SharedFlag, SharedPoint


class CalibrationWindow(QMainWindow):
    def __init__(self, target_coordinates: SharedPoint, target_clicked: SharedFlag):
        super().__init__()
        self.target_coordinates = target_coordinates
        self.target_clicked = target_clicked
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        screens = QApplication.screens()
        self.button = QPushButton(self)
        self.button.setStyleSheet('background-color: rgb(192, 192, 192)')
        self.button.clicked.connect(self.on_clicked)

        # Если есть второй экран, перемещаем окно на него
        if len(screens) > 1:
            screen_geometry = screens[-1].availableGeometry()
            self.setGeometry(screen_geometry)
            self.showFullScreen()
        else:
            self.showMaximized()

        # self.overlay = ObjectsPainter(self.video_label)
        # self.overlay.setGeometry(self.video_label.geometry())
        # self.overlay.show()
        self.setStyleSheet('background-color: black')
        self.refresh_timer = self.startTimer(int(FPS_120 * 2 * MSEC_IN_SEC))

    @pyqtSlot()
    def on_clicked(self):
        self.target_clicked.set(True)

    def timerEvent(self, a0: QTimerEvent):
        self.button.move(QPoint(*self.target_coordinates.array[:]))
        # TODO: paint figure at coordinates from GazePredictor


    def adjust(self):
        self.main_widget.adjustSize()
        self.adjustSize()