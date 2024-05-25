from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMouseEvent, QKeyEvent
from PyQt6.QtWidgets import QLabel

from tracker.utils.coordinates import Point


class CallbacksLabel(QLabel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.on_mouse_click: Optional[Callable] = None
        self.on_mouse_move: Optional[Callable] = None
        self.on_mouse_release: Optional[Callable] = None
        self.on_enter_press: Optional[Callable] = None

    def mousePressEvent(self, ev: QMouseEvent):
        super().mousePressEvent(ev)
        if self.on_mouse_click:
            self.on_mouse_click(Point(ev.pos().x(), ev.pos().y()))

    def mouseMoveEvent(self, ev: QMouseEvent):
        super().mouseMoveEvent(ev)
        if self.on_mouse_move:
            self.on_mouse_move(Point(ev.pos().x(), ev.pos().y()))

    def mouseReleaseEvent(self, ev: QMouseEvent):
        super().mouseReleaseEvent(ev)
        if self.on_mouse_release:
            self.on_mouse_release(Point(ev.pos().x(), ev.pos().y()))

    def keyPressEvent(self, ev: QKeyEvent):
        key = ev.key()
        if key == Qt.Key.Key_Enter or key == Qt.Key.Key_Return:
            if self.on_enter_press:
                self.on_enter_press()
