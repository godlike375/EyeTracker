import asyncio
from time import sleep
import sys
from functools import partial

import cv2
import numpy
import websockets
from time import sleep
from multiprocessing import Process, Queue

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from eye_tracker.tracker.command_processor import CommandExecutor
from eye_tracker.tracker.protocol import Command, Commands, Coordinates, StartTracking, ImageWithCoordinates
from eye_tracker.tracker.abstractions import ID
from eye_tracker.tracker.fps_counter import FPSCounter

class DataStreamProcessor:
    def __init__(self, url, images_stream, command_stream):
        self.url = url
        self.connection = None
        self.update_image = None
        self.commands = CommandExecutor()
        self.fps = FPSCounter()
        self.images_stream: Queue = images_stream
        self.command_stream: Queue = command_stream

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
        while True:
            if not self.command_stream.empty():
                cmd: Command = self.command_stream.get(block=False)
                await self.connection.send(cmd.pack())

            msg: bytes = await self.connection.recv()
            imcords = ImageWithCoordinates.unpack(msg)
            sleep(0.00001) # WARNING: somehow it saves main window from freezing. looks like it's connected with Queues
            self.images_stream.put(imcords)
            if self.fps.able_to_calculate():
                print(f'main fps {self.fps.calculate()}')
                #print(len(msg))
            #print(f'processor frame id {imcords.image.id}')
            self.fps.count_frame()

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.video_label = QLabel()
        layout = QVBoxLayout()
        layout.addWidget(self.video_label)
        self.setLayout(layout)
        self.images_stream = Queue(maxsize=1)
        self.command_stream = Queue(maxsize=1)
        self.url = 'ws://localhost:5680'
        self.data_stream = DataStreamProcessor(self.url, self.images_stream,
                                               self.command_stream)
        self.data_stream_process = Process(target=self.data_stream.run)
        self.data_stream_process.start()

        self.video_size_set = False
        self.free_tracker_id: ID = ID(0)
        self.frame_id: ID = ID(0)

        self.timer = self.startTimer(4)
        self.fps = FPSCounter()
        self.prev_frame = numpy.zeros((480, 640, 3))

    def timerEvent(self, id) -> None:
        self.update_video_frame()

    def update_video_frame(self):
        if self.images_stream.empty():
            return
        imcords: ImageWithCoordinates = self.images_stream.get(block=False)
        self.frame_id = imcords.image.id
        #print(f'main frame id {imcords.image.id}')
        # TODO: draw coords

        frame = imcords.image.to_raw_image().astype(numpy.uint8)
        for c in imcords.coords:
            frame = cv2.rectangle(frame, (int(c.x1), int(c.y1)), (int(c.x2), int(c.y2)), color=(255, 0, 0), thickness=2)

        if self.fps.able_to_calculate():
            print(f'update fps {self.fps.calculate()}')
        if not (frame == self.prev_frame).all():
            self.fps.count_frame()
        self.prev_frame = frame

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
        self.command_stream.put(cmd)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
