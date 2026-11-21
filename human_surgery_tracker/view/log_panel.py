import logging

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDockWidget, QPlainTextEdit

from tracker.utils.logger import logger

MAX_LOG_BLOCKS = 2000
LOG_FORMAT = "[%(levelname)s] %(asctime)s %(filename)s:%(lineno)d - %(message)s"
DATE_FORMAT = "%H:%M:%S"


class LogEmitter(QObject):
    message = Signal(str)


class _QtLogHandler(logging.Handler):
    def __init__(self, emitter: LogEmitter):
        super().__init__()
        self._emitter = emitter

    def emit(self, record):
        try:
            self._emitter.message.emit(self.format(record))
        except Exception:
            pass


class LogPanel(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Log", parent)
        self.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self._view = QPlainTextEdit()
        self._view.setReadOnly(True)
        self._view.setMaximumBlockCount(MAX_LOG_BLOCKS)
        self._view.setFont(QFont("Consolas", 9))
        self.setWidget(self._view)
        self.setMinimumWidth(300)

        self._emitter = LogEmitter()
        self._emitter.message.connect(self._append, Qt.ConnectionType.QueuedConnection)
        self._handler = _QtLogHandler(self._emitter)
        self._handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        self._handler.setLevel(logger.level)
        logger.addHandler(self._handler)

    def _append(self, text: str):
        self._view.appendPlainText(text)

    def clear(self):
        self._view.clear()
