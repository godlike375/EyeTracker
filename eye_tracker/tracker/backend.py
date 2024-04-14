import asyncio
import queue
from asyncio import Future
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
#from multiprocessing import Queue
from queue import Queue

import websockets

import cv2
from websockets import WebSocketServerProtocol

from eye_tracker.tracker.image import CompressedImage
from eye_tracker.tracker.protocol import Command, Commands, Coordinates, ImageWithCoordinates, StartTracking
from eye_tracker.tracker.abstractions import ID
from eye_tracker.tracker.fps_counter import FPSCounter
from eye_tracker.tracker.tracker import TrackerWrapper


class WebCam:
    def __init__(self):
        self.image_id: ID = ID(0)

        self.frames = Queue(maxsize=2)
        self.thread = Thread(target=self.mainloop, daemon=True)
        self.thread.start()

    def mainloop(self):
        self.camera = cv2.VideoCapture(0)
        #self.ret, self.frame = self.camera.read()
        self.camera.set(cv2.CAP_PROP_FPS, 60)
        while True:
            self.frames.put(self.capture_jpeg())

    def __del__(self):
        self.camera.release()

    def capture_jpeg(self) -> CompressedImage:
        ret, frame = self.camera.read()
        #jpeg = CompressedImage.from_raw_image(self.frame, self.image_id)
        jpeg = CompressedImage.from_raw_image(frame, self.image_id)
        self.image_id += 1
        #return jpeg if self.ret else None
        return jpeg if ret else None


class WebSocketServer:
    def __init__(self):
        self.frontend: WebSocketServerProtocol = None
        self.elvis: WebSocketServerProtocol = None
        self.camera = WebCam()
        self.fps = FPSCounter()
        self.trackers: dict[int, TrackerWrapper] = {}
        self.executor = ThreadPoolExecutor()

    async def start(self):
        async with  websockets.serve(self.accept_frontend, 'localhost', 5680):
            await Future()

    def send_to_tracker(self, tracker: TrackerWrapper, img: bytes):
        while True:
            try:
                tracker.video_stream.put_nowait(img)
                break
            except queue.Full:
                continue

    async def _send_to_trackers(self, img: bytes):
        trackers = self.trackers.values()
        #executor = ThreadPoolExecutor()  # WARNING: without new executor
        # program stuck and crashes at 1 or 2 trackers not more
        send_to_trackers = [
            asyncio.get_running_loop().run_in_executor(self.executor, self.send_to_tracker, tracker, img)
            for tracker in trackers]
        await asyncio.gather(*send_to_trackers)

    def receive_from_tracker(self, tracker: TrackerWrapper, results: list):
        while True:
            try:
                results.append(tracker.coordinates_commands_stream.get_nowait())
                break
            except queue.Empty:
                continue

    async def _receive_from_trackers(self) -> list[Coordinates]:
        coordinates: list[Coordinates] = []
        trackers = self.trackers.values()
        #executor = ThreadPoolExecutor() # WARNING: without new executor
        # program stuck and crashes at 1 or 2 trackers not more
        send_to_trackers = [
            asyncio.get_running_loop().
            run_in_executor(self.executor,
                            self.receive_from_tracker, tracker, coordinates)
            for tracker in trackers]
        await asyncio.gather(*send_to_trackers)
        return coordinates

    async def stream_video(self):
        while True:
            jpeg: CompressedImage = self.camera.frames.get()
            packed = jpeg.pack()
            await self._send_to_trackers(packed)
            coordinates = []
            coordinates = await self._receive_from_trackers()
            jpeg_with_coordinates = ImageWithCoordinates(jpeg, coordinates)
            await self.frontend.send(jpeg_with_coordinates.pack())
            if self.fps.able_to_calculate():
                print(f'backend fps: {self.fps.calculate()}')
            self.fps.count_frame()

    async def receive_frontend_commands(self):
        while True:
            cmd_msg = await self.frontend.recv()
            command = Command.unpack(cmd_msg)
            match command.type:
                case Commands.START_TRACKING:
                    com_data: StartTracking = command.data
                    tracker = TrackerWrapper(com_data.tracker_id, com_data.coords)
                    self.trackers[com_data.tracker_id] = tracker

    async def accept_frontend(self, websocket: WebSocketServerProtocol, path):
        name = await websocket.recv()
        match name:
            case 'frontend':
                self.frontend = websocket
            case 'elvis':
                self.elvis = websocket

        try:
            await asyncio.gather(self.stream_video(), self.receive_frontend_commands())
        except websockets.exceptions.ConnectionClosed:
            self.frontend = None
            # TODO: unregister elvis
            print('Client disconnected')


if __name__ == "__main__":
    server = WebSocketServer()
    asyncio.run(server.start())
