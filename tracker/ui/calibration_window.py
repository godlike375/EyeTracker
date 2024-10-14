import typing
from PyQt6.QtCore import Qt, QPoint, pyqtSlot
from PyQt6.QtCore import QTimerEvent
from PyQt6.QtWidgets import QMainWindow, QApplication, QPushButton, QWidget, QVBoxLayout, QLabel
from PyQt6.uic.properties import QtGui

from tracker.utils.fps import FPS_120, MSEC_IN_SEC
from tracker.utils.shared_objects import SharedFlag, SharedPoint


class CalibrationWindow(QMainWindow):
    def __init__(self, target_coordinates: SharedPoint, target_clicked: SharedFlag):
        super().__init__()
        self.target_coordinates = target_coordinates
        self.target_accepted = target_clicked
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        screens = QApplication.screens()
        # Если есть второй экран, перемещаем окно на него
        self.setGeometry(screens[-1].availableGeometry())
        self.control_window = QWidget(self)
        if len(screens) > 1:
            self.control_window.setGeometry(screens[0].availableGeometry())
        else:
            self.control_window.move(screens[0].availableGeometry().center())
        layout = QVBoxLayout(self.control_window)
        self.label = QLabel('Нажмите Enter для продолжения', self.control_window)
        layout.addWidget(self.label)
        self.control_window.setLayout(layout)
        self.control_window.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.control_window.setStyleSheet('background-color: rgb(192, 192, 192)')
        self.control_window.show()

        self.showFullScreen()

        # self.overlay = ObjectsPainter(self.video_label)
        # self.overlay.setGeometry(self.video_label.geometry())
        # self.overlay.show()
        self.setStyleSheet('background-color: rgb(40, 40, 40)')
        self.refresh_timer = self.startTimer(20)

    def timerEvent(self, a0: QTimerEvent):
        ...
        # TODO: paint figure at coordinates from GazePredictor


    # def adjust(self):
    #     self.main_widget.adjustSize()
    #     self.adjustSize()