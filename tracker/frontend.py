import asyncio
import sys
from functools import partial

import cv2
import numpy
from PyQt6.QtCore import QThread, pyqtSignal, QSize, Qt, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
import websockets

sys.path.append('..')

from tracker.command_processor import CommandExecutor
from tracker.protocol import Command, Commands, Coordinates, StartTracking, \
    ImageWithCoordinates
from tracker.abstractions import ID
from tracker.fps_counter import FPSCounter

import sys


FPS_25 = 1/25


class DataStreamProcessor(QThread):
    update_image = pyqtSignal(object)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.connection = None
        self.fps = FPSCounter(2)
        self.throttle = FPSCounter(FPS_25)
        self.commands = CommandExecutor()

    def run(self):
        asyncio.run(self.connect())

    async def connect(self):
        async with websockets.connect(self.url, timeout=10) as websocket:
            await websocket.send('frontend')
            self.connection = websocket
            await self.mainloop()

    def send_command(self, command: Command):
        func = partial(self.connection.send, command.pack())
        self.commands.queue_command(func)


    async def mainloop(self):
        try:
            while True:
                await self.commands.exec_queued_commands()
                msg: bytes = await self.connection.recv()
                if self.throttle.able_to_calculate():
                    self.throttle.calculate()
                    imcords = ImageWithCoordinates.unpack(msg)
                    self.update_image.emit(imcords)
                if self.fps.able_to_calculate():
                    print(f'frontend fps: {self.fps.calculate()}')
                #print(f'processor frame id {imcords.image.id}')
                self.fps.count_frame()
                self.throttle.count_frame()


        except Exception as e:
            print("Exception in async mainloop:", e)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.video_label = QLabel()
        layout = QVBoxLayout()
        layout.addWidget(self.video_label)
        self.setLayout(layout)

        self.data_stream = DataStreamProcessor('ws://localhost:5680')
        self.data_stream.update_image.connect(self.update_video_frame, Qt.ConnectionType.QueuedConnection)
        self.video_size_set = False
        self.free_tracker_id: ID = ID(0)
        self.frame_id: ID = ID(0)
        self.data_stream.start()

    @pyqtSlot(object)
    def update_video_frame(self, imcords: ImageWithCoordinates):
        self.frame_id = imcords.image.id
        #print(f'main frame id {imcords.image.id}')
        # TODO: draw coords
        frame = imcords.image.to_raw_image().astype(numpy.uint8)
        for c in imcords.coords:
            if c is None:
                continue
            frame = cv2.rectangle(frame, (int(c.x1), int(c.y1)), (int(c.x2), int(c.y2)), color=(255, 0, 0), thickness=2)

        image = QImage(frame, frame.shape[1], frame.shape[0], QImage.Format.Format_BGR888)
        pixmap = QPixmap.fromImage(image)
        self.video_label.setPixmap(pixmap)

        if not self.video_size_set:
            self.video_label.setFixedSize(QSize(frame.shape[1], frame.shape[0]))
            self.video_size_set = True

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Enter or key == Qt.Key.Key_Return:
            self.start_tracking()

    def start_tracking(self):
        start_data = StartTracking(Coordinates(270, 190, 370, 290), self.frame_id, self.free_tracker_id)
        self.free_tracker_id += 1
        cmd = Command(Commands.START_TRACKING, start_data)
        self.data_stream.send_command(cmd)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())