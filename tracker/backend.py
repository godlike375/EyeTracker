import argparse
import asyncio
import multiprocessing
import sys
from asyncio import Future
from threading import Thread
from queue import Queue
import websockets

import cv2
from websockets import WebSocketServerProtocol

sys.path.append('..')

from tracker.image import CompressedImage, PREFER_PERFORMANCE_OVER_QUALITY
from tracker.protocol import Command, Commands, Coordinates, ImageWithCoordinates, StartTracking
from tracker.abstractions import ID, try_few_times
from tracker.fps_counter import FPSCounter
from tracker.object_tracker import TrackerWrapper, FPS_120


class WebCam:
    def __init__(self, benchmark = False):
        self.image_id: ID = ID(0)

        self.frames = Queue(maxsize=3)
        self.thread = Thread(target=self.mainloop, daemon=True)
        self.thread.start()
        self.benchmark = benchmark

    def mainloop(self):
        self.camera = cv2.VideoCapture(0)
        self.camera.set(cv2.CAP_PROP_FPS, 60)
        if self.benchmark:
            self.ret, self.frame = self.camera.read()
            while True:
                self.frames.put(self.capture_image_benchmark())
        else:
            while True:
                self.frames.put(self.capture_image())

    def __del__(self):
        self.camera.release()

    def capture_image(self) -> CompressedImage:
        ret, frame = self.camera.read()
        #frame = resize_frame_relative(frame, 0.5)
        jpeg = CompressedImage.from_raw_image(frame, self.image_id, quality=PREFER_PERFORMANCE_OVER_QUALITY)
        self.image_id += 1
        return jpeg if ret else None

    def capture_image_benchmark(self) -> CompressedImage:
        jpeg = CompressedImage.from_raw_image(self.frame, self.image_id, quality=PREFER_PERFORMANCE_OVER_QUALITY)
        self.image_id += 1
        return jpeg if self.ret else None


class WebSocketServer:
    def __init__(self, benchmark = False):
        self.frontend: WebSocketServerProtocol = None
        self.elvis: WebSocketServerProtocol = None
        self.camera = WebCam(benchmark)
        self.fps = FPSCounter(1.5)
        self.trackers: dict[int, TrackerWrapper] = {}

    async def start(self):
        async with  websockets.serve(self.accept_frontend, 'localhost', 5680):
            await Future()

    def send_to_tracker(self, tracker: TrackerWrapper, img: bytes):
        try_few_times(lambda: tracker.video_stream.put_nowait(img), interval=FPS_120 / 3, times=3)

    async def _send_to_trackers(self, img: bytes):
        trackers = self.trackers.values()
        send_to_trackers = [
            asyncio.get_running_loop().run_in_executor(None, self.send_to_tracker, tracker, img)
            for tracker in trackers]
        await asyncio.gather(*send_to_trackers)

    def receive_from_tracker(self, tracker: TrackerWrapper, results: list):
        try_few_times(lambda : results.append(tracker.coordinates_commands_stream.get_nowait()),
                      interval=FPS_120, times=1)

    async def _receive_from_trackers(self, coordinates: list[Coordinates]) -> list[Coordinates]:
        trackers = self.trackers.values()
        send_to_trackers = [
            asyncio.get_running_loop().
            run_in_executor(None, self.receive_from_tracker, tracker, coordinates)
            for tracker in trackers]
        await asyncio.gather(*send_to_trackers)
        return coordinates

    async def stream_video(self):
        while True:
            jpeg: CompressedImage = self.camera.frames.get()
            packed = jpeg.pack()
            coordinates = []
            await asyncio.gather(self._send_to_trackers(packed), self._receive_from_trackers(coordinates))
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
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--benchmark',
                        action='store_true')
    args = parser.parse_args(sys.argv[1:])
    server = WebSocketServer(args.benchmark)
    asyncio.run(server.start())
