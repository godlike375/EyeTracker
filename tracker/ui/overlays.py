from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QPaintEvent
from PyQt6.QtCore import Qt, QRect, QPoint

from tracker.utils.coordinates import BoundingBox


class ObjectsPainter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Widget | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.painter = QPainter(self)
        self.pen = QPen(QColor(255, 0, 0, 255))
        self.pen.setWidth(10)
        self.painter.setPen(self.pen)

    def paint_rects(self, coordinates: list[BoundingBox]):
        painter = QPainter(self)
        painter.setPen(self.pen)
        for c in coordinates:
            painter.drawRect(QRect(QPoint(c.x1, c.y1), QPoint(c.x2, c.y2)))

    def paintEvent(self, a0: QPaintEvent):
        ...
        # painter = QPainter(self)
        # painter.setPen(self.pen)
        # painter.drawRect(self.rect())