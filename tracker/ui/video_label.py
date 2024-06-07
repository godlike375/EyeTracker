from typing import Callable, Optional

import numpy
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QMouseEvent, QKeyEvent, QImage, QPixmap
from PyQt6.QtWidgets import QLabel

from tracker.utils.coordinates import Point, get_translation_maxtix_between_resolutions, translate_coordinates
from tracker.utils.image_processing import resize_frame_relative


class CallbacksVideoLabel(QLabel):

    def __init__(self, resized_resolution: tuple[int, int] = (480, 640), parent=None):
        super().__init__(parent)
        self.new_width = 640
        self.new_height = 480
        self.scale = 1
        self.resized_to_original = None
        #self.resized_to_original = None
        self.on_mouse_click: Optional[Callable] = None
        self.on_mouse_move: Optional[Callable] = None
        self.on_mouse_release: Optional[Callable] = None
        self.on_enter_press: Optional[Callable] = None
        self.video_size_set = False
        self.portrait_oriented = False

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
        if width > height:
            new_width = 860 # WARNING TODO: strange bug looking if the value is 950 or 945 for example
            scale = new_width / width
        else:
            new_height = 620 # WARNING TODO: strange bug looking if the value is 580 for example
            scale = new_height / height
        self.new_width = int(width * scale)
        self.new_height = int(height * scale)
        self.resized_to_original = get_translation_maxtix_between_resolutions(self.new_width, self.new_height, width, height)
        return scale
        #self.resized_to_original = get_translation_maxtix_between_resolutions(*self.resized, width, heigth)

    def set_frame(self, frame: numpy.ndarray):
        if self.resized_to_original is None:
            height = frame.shape[0]
            width = frame.shape[1]
            if height > width:
                self.portrait_oriented = True
            self.scale = self.setup_rescaling(height, width)
        # rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # rgb = Image.fromarray(rgb) TODO: maybe faster?

        frame = resize_frame_relative(frame, self.scale)
        image = QImage(frame, self.new_width, self.new_height, QImage.Format.Format_BGR888)
        pixmap = QPixmap.fromImage(image)
        self.setPixmap(pixmap)

        if not self.video_size_set:
            self.setFixedSize(QSize(frame.shape[1], frame.shape[0]))
            self.video_size_set = True
