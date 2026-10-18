from PySide6.QtCore import QTimer, Qt, QPoint
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from model.interfaces import StatusMessage

TOAST_MARGIN = 12
TOAST_SPACING = 8
DEFAULT_DURATION_MS = 3500
ERROR_DURATION_MS = 6000

LEVEL_STYLES = {
    StatusMessage.INFO.value: "background-color: rgba(40, 40, 40, 220); color: #ffffff;",
    StatusMessage.WARNING.value: "background-color: rgba(180, 120, 0, 230); color: #ffffff;",
    StatusMessage.ERROR.value: "background-color: rgba(170, 30, 30, 235); color: #ffffff;",
}


class Toast(QFrame):
    def __init__(self, text: str, level: str, parent: QWidget):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet(
            f"border-radius: 6px; padding: 8px 14px; {LEVEL_STYLES.get(level, LEVEL_STYLES[StatusMessage.INFO.value])}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("background: transparent; color: #ffffff; font-size: 12px;")
        layout.addWidget(label)
        self.adjustSize()

        duration = ERROR_DURATION_MS if level == StatusMessage.ERROR.value else DEFAULT_DURATION_MS
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._expire)
        self._timer.start(duration)
        self._on_expire = None

    def set_on_expire(self, callback):
        self._on_expire = callback

    def _expire(self):
        if self._on_expire:
            self._on_expire(self)
        else:
            self.deleteLater()


class ToastManager:
    def __init__(self, window: QWidget, anchor: QWidget):
        self._window = window
        self._anchor = anchor
        self._toasts = []

    def show_message(self, text: str, level=StatusMessage.INFO):
        level_value = level.value if isinstance(level, StatusMessage) else str(level)
        toast = Toast(text, level_value, self._window)
        toast.set_on_expire(self._remove)
        self._toasts.append(toast)
        toast.show()
        toast.raise_()
        self._relayout()

    def _remove(self, toast):
        if toast in self._toasts:
            self._toasts.remove(toast)
        toast.deleteLater()
        self._relayout()

    def clear(self):
        for toast in list(self._toasts):
            self._remove(toast)

    def _relayout(self):
        anchor = self._anchor
        top_left = anchor.mapTo(self._window, QPoint(0, 0))
        center_x = top_left.x() + anchor.width() // 2
        y = top_left.y() + TOAST_MARGIN
        for toast in self._toasts:
            toast.adjustSize()
            w = min(toast.sizeHint().width(), max(anchor.width() - 2 * TOAST_MARGIN, 100))
            toast.setFixedWidth(w)
            toast.move(center_x - w // 2, y)
            y += toast.height() + TOAST_SPACING
