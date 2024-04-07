import io
import sys

import cv2
import numpy as np
from PIL.Image import Image
import PIL.Image
from PyQt6.QtCore import QThread, pyqtSignal, QSize, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
import websocket


from eye_tracker.tracker.fps_counter import FPSCounter

# works a 10% faster than imdecode
def decode_jpeg_to_image(jpeg_data):
    with io.BytesIO(jpeg_data) as input_buffer:
        decoded_image = PIL.Image.open(input_buffer)  # Открываем изображение из буфера
        decoded_image = decoded_image.convert("RGB")  # Преобразуем в RGB, если это необходимо
    return decoded_image


class VideoStreamThread(QThread):
    frame_signal = pyqtSignal(bytes)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.ws: websocket.WebSocketApp = None

    def run(self):
        def on_message(ws, message):
            self.frame_signal.emit(message)

        while True:
            try:
                self.ws = websocket.WebSocketApp(self.url, on_message=on_message)
                self.ws.run_forever()
            except:
                ...


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.fps = FPSCounter()
        self.video_label = QLabel()
        layout = QVBoxLayout()
        layout.addWidget(self.video_label)
        self.setLayout(layout)

        self.video_thread = VideoStreamThread('ws://localhost:5680')
        self.video_thread.frame_signal.connect(self.update_video_frame)
        self.video_thread.start()
        self.video_size_set = False

    def update_video_frame(self, frame):
        frame = decode_jpeg_to_image(frame)
        frame = np.asarray(frame)
        if self.fps.able_to_calculate():
            print(self.fps.calculate())
        self.fps.frames += 1

        image = QImage(frame, frame.shape[1], frame.shape[0], QImage.Format.Format_BGR888)
        pixmap = QPixmap.fromImage(image)
        self.video_label.setPixmap(pixmap)

        if not self.video_size_set:
            self.video_label.setFixedSize(QSize(frame.shape[1], frame.shape[0]))
            self.video_size_set = True

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Enter or key == Qt.Key.Key_Return:
            self.video_thread.ws.send('hello motherfucker')
        #    self.start_tracking()

    def start_tracking(self):
        # Отправить команду на Backend для начала отслеживания объекта с заданными координатами
        pass


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
