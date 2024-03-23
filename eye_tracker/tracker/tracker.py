import cv2
import asyncio
import websockets
import dlib
import time
import numpy as np

import sys
sys.setswitchinterval(0.00000001)


def bytes_to_numpy(serialized_arr: str) -> np.array:
    sep = '|'.encode('utf-8')
    i_0 = serialized_arr.find(sep)
    i_1 = serialized_arr.find(sep, i_0 + 1)
    arr_dtype = serialized_arr[:i_0].decode('utf-8')
    arr_shape = tuple([int(a) for a in serialized_arr[i_0 + 1:i_1].decode('utf-8').split(',')])
    arr_str = serialized_arr[i_1 + 1:]
    arr = np.frombuffer(arr_str, dtype = arr_dtype).reshape(arr_shape)
    return arr

class FPSCounter:
    def __init__(self):
        self.start_time = time.time()
        self.frames = 0

    def calculate(self):
        current_time = time.time()
        elapsed_time = current_time - self.start_time

        if elapsed_time >= 1.0:
            fps = self.frames / elapsed_time
            self.frames = 0
            self.start_time = current_time
            return fps
        else:
            return 0

    def able_to_calculate(self):
        current_time = time.time()
        elapsed_time = current_time - self.start_time

        if elapsed_time >= 1.0:
            return True
        else:
            return False


class ObjectTrackerClient:
    def __init__(self):
        self.tracker = None
        self.start_time = time.time()
        self.fps_cnt = FPSCounter()

    async def track_object(self, frame_str):
        #frame = cv2.imdecode(np.fromstring(frame_str, dtype=np.uint8), cv2.IMREAD_COLOR)
        frame = bytes_to_numpy(frame_str)
        if self.tracker is None:
            # Инициализация трекера
            self.tracker = dlib.correlation_tracker()
            self.tracker.start_track(frame, dlib.rectangle(0, 0, frame.shape[1], frame.shape[0]))
        else:
            # Обновление трекера с новыми координатами
            self.tracker.update(frame)

        # Получение текущих координат объекта
        track_rect = self.tracker.get_position()
        x, y, w, h = int(track_rect.left()), int(track_rect.top()), int(track_rect.width()), int(track_rect.height())

        # Отображение координат объекта на кадре (или другая обработка)
        #cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # Отображение кадра с объектом
        #cv2.imshow('Tracked Object', frame)
        #cv2.waitKey(1)

        # Увеличение счетчика кадров
        if self.fps_cnt.able_to_calculate():
            print(self.fps_cnt.calculate())
        self.fps_cnt.frames += 1

    async def receive_frames(self):
        while True:
            try:
                async with websockets.connect('ws://localhost:8000') as websocket:
                    while True:
                        frame_str = await websocket.recv()
                        await self.track_object(frame_str)
            except websockets.exceptions.ConnectionClosedError:
                pass

    def start(self):
        asyncio.run(self.receive_frames())

client = ObjectTrackerClient()
client.start()
