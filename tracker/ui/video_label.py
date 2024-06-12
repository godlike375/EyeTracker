from typing import Callable, Optional

import cv2
import numpy
from PyQt6.QtCore import Qt, QSize, pyqtSlot
from PyQt6.QtGui import QMouseEvent, QKeyEvent, QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QApplication

from tracker.utils.coordinates import Point, get_translation_maxtix_between_resolutions, translate_coordinates
from tracker.utils.image_processing import resize_frame_relative


class CallbacksVideoLabel(QLabel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.new_width = 640
        self.new_height = 480
        self.scale = 1
        self.resized_to_original = None
        self.on_mouse_click: Optional[Callable] = None
        self.on_mouse_move: Optional[Callable] = None
        self.on_mouse_release: Optional[Callable] = None
        self.on_enter_press: Optional[Callable] = None
        self.portrait_oriented = False
        self.rotate_degree = 0

    def mousePressEvent(self, ev: QMouseEvent):
        super().mousePressEvent(ev)
        if self.on_mouse_click:
            translated = translate_coordinates(self.resized_to_original, Point(ev.pos().x(), ev.pos().y()))
            self.on_mouse_click(translated)

    def mouseMoveEvent(self, ev: QMouseEvent):
        super().mouseMoveEvent(ev)
        if self.on_mouse_move:
            translated = translate_coordinates(self.resized_to_original, Point(ev.pos().x(), ev.pos().y()))
            self.on_mouse_move(translated)

    def mouseReleaseEvent(self, ev: QMouseEvent):
        super().mouseReleaseEvent(ev)
        if self.on_mouse_release:
            translated = translate_coordinates(self.resized_to_original, Point(ev.pos().x(), ev.pos().y()))
            self.on_mouse_release(translated)

    def keyPressEvent(self, ev: QKeyEvent):
        key = ev.key()
        if key == Qt.Key.Key_Enter or key == Qt.Key.Key_Return:
            if self.on_enter_press:
                self.on_enter_press()

    def setup_rescaling(self, height: int, width: int):
        available = QApplication.primaryScreen().availableGeometry()
        # TODO: refactor
        if width > height:
            new_width = int(available.width() // 1.3)
            scale = new_width / width
        else:
            new_height = int(available.height() // 1.3)
            scale = new_height / height
        self.new_width = int(width * scale)
        if self.new_width > available.width():
            self.new_width = int(available.width() // 1.3)
            scale = self.new_width / width

        self.new_height = int(height * scale)
        if self.new_height > available.height():
            self.new_height = int(available.height() // 1.3)
            scale = self.new_height / height
            self.new_width = int(width * scale)

        self.resized_to_original = get_translation_maxtix_between_resolutions(self.new_width, self.new_height, width, height)
        return scale

    def set_frame(self, frame: numpy.ndarray):
        if self.resized_to_original is None:
            height = frame.shape[0]
            width = frame.shape[1]
            if height > width:
                self.portrait_oriented = True
            self.scale = self.setup_rescaling(height, width)
            self.setFixedSize(QSize(self.new_width, self.new_height))
            self.parent().parent().adjust()

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = resize_frame_relative(frame, self.scale)
        bytes_per_line = 3 * frame.shape[1]
        image = QImage(frame, frame.shape[1], frame.shape[0], bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(image)
        self.setPixmap(pixmap)

    @pyqtSlot(int)
    def on_rotate(self, degree: int):
        self.resized_to_original = None

