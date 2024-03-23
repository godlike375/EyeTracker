import cv2
import asyncio
import websockets
import dlib
import time
import numpy as np

class ObjectTrackerClient:
    def __init__(self):
        self.tracker = None
        self.frame_count = 0
        self.start_time = time.time()

    async def track_object(self, frame_str):
        frame = cv2.imdecode(np.fromstring(frame_str, dtype=np.uint8), cv2.IMREAD_COLOR)

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
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # Отображение кадра с объектом
        cv2.imshow('Tracked Object', frame)
        cv2.waitKey(1)

        # Увеличение счетчика кадров
        self.frame_count += 1

    async def print_fps(self):
        while True:
            await asyncio.sleep(1)  # Ожидание 1 секунды
            elapsed_time = time.time() - self.start_time
            fps = self.frame_count / elapsed_time
            print(f"FPS: {fps}")

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
        loop = asyncio.get_event_loop()
        loop.create_task(self.print_fps())
        loop.create_task(self.receive_frames())
        loop.run_forever()

client = ObjectTrackerClient()
client.start()
