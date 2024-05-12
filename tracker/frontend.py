import argparse
import asyncio
import multiprocessing
import sys
from functools import partial
from multiprocessing.shared_memory import SharedMemory

import cv2
import numpy
from PyQt6.QtCore import pyqtSignal, QSize, Qt, pyqtSlot, QTimerEvent, QObject
from PyQt6.QtGui import QImage, QPixmap, QAction
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget, QMainWindow

from tracker.gaze_predictor_backend import GazePredictorBackend
from tracker.camera_streamer import create_camera_streamer
from tracker.object_tracker import TrackerWrapper
from tracker.overlays import ObjectsPainter

sys.path.append('..')

from tracker.command_processor import AsyncCommandExecutor
from tracker.protocol import Command, Commands, Coordinates, \
    ImageWithCoordinates
from tracker.abstractions import ID
from tracker.fps_counter import FPSCounter


FPS_50 = 1 / 50


class MainWindow(QMainWindow):
    new_tracker = pyqtSignal(Coordinates)
    def __init__(self):
        super().__init__()
        self.video_label = QLabel()
        layout = QVBoxLayout()
        layout.addWidget(self.video_label)

        self.overlay = ObjectsPainter(self.video_label)
        self.overlay.setGeometry(self.video_label.geometry())
        self.overlay.show()

        self.menu_bar = self.menuBar()

        select_pupil = self.menu_bar.addMenu('Выделение зрачка')
        start_select = QAction('Начать', self)
        # start.triggered.connect()
        end_select = QAction('Остановить', self)

        select_pupil.menuAction().triggered.connect(self.selection_started)
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
        key = event.key()
        if key == Qt.Key.Key_Enter or key == Qt.Key.Key_Return:
            self.new_tracker.emit(Coordinates(270, 190, 370, 290))

    @pyqtSlot()
    def selection_started(self):
        print('select')


class Frontend(QObject):

    def __init__(self, parent: MainWindow, id_camera: int = 0, fps=120, resolution=640):
        super().__init__(parent)
        self.video_frame, self.video_stream_process, self.shared_memory =\
            create_camera_streamer(id_camera, fps, resolution)

        self.trackers: dict[ID, TrackerWrapper] = {}

        #self.calibrator_backend = GazePredictorBackend()
        self.window = parent

        self.fps = FPSCounter(2)
        self.throttle = FPSCounter(FPS_50)
        self.refresh_timer = self.startTimer(int(FPS_50 * 1000))

        self.free_tracker_id: ID = ID(0)

    def timerEvent(self, a0: QTimerEvent):
        if self.throttle.able_to_calculate():
            self.throttle.calculate()
            # TODO: get coordinates
            coords = [Coordinates(*t.coordinates_memory[:]) for t in self.trackers.values()]
            frame = numpy.copy(self.video_frame)
            for c in coords:
                frame = cv2.rectangle(frame, (int(c.x1), int(c.y1)), (int(c.x2), int(c.y2)), color=(255, 0, 0),
                                      thickness=2)
            self.window.update_video_frame(frame)

        if self.fps.able_to_calculate():
            print(f'frontend fps: {self.fps.calculate()}')
        self.fps.count_frame()

    @pyqtSlot(Coordinates)
    def on_new_tracker_requested(self, coords: Coordinates):
        self.free_tracker_id += 1
        tracker = TrackerWrapper(self.free_tracker_id, coords, self.shared_memory)
        self.trackers[self.free_tracker_id] = tracker



if __name__ == '__main__':
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--id_camera',
                        type=int, default=0)
    parser.add_argument('-f', '--fps',
                        type=int, default=120)
    parser.add_argument('-r', '--resolution',
                        type=int, default=640)
    args = parser.parse_args(sys.argv[1:])

    app = QApplication(sys.argv)
    window = MainWindow()
    frontend = Frontend(window, args.id_camera, args.fps, args.resolution)
    window.new_tracker.connect(frontend.on_new_tracker_requested)
    window.show()
    sys.exit(app.exec())