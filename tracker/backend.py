import argparse
import asyncio
import multiprocessing
import sys
from asyncio import Future
from threading import Thread, RLock
from queue import Queue

import numpy
import websockets
from multiprocessing.shared_memory import SharedMemory

import cv2
from websockets import WebSocketServerProtocol

sys.path.append('..')

from tracker.image import CompressedImage, PREFER_PERFORMANCE_OVER_QUALITY, resize_frame_relative
from tracker.protocol import Command, Commands, Coordinates, ImageWithCoordinates, StartTracking
from tracker.abstractions import ID, try_few_times
from tracker.fps_counter import FPSCounter
from tracker.object_tracker import TrackerWrapper, FPS_120
from time import sleep


class WebCam:
    def __init__(self, benchmark = False, id_camera = 0):
        self.image_id: ID = ID(0)
        self.benchmark = benchmark
        self.id_camera = id_camera
        self.shared_frame_mem = None
        self.initialization_lock = RLock()

        self.thread = Thread(target=self.mainloop, daemon=True)
        self.thread.start()


    def mainloop(self):
        self.initialization_lock.acquire()
        self.camera = cv2.VideoCapture(self.id_camera)
        self.camera.set(cv2.CAP_PROP_FPS, 60)
        self.ret, self.frame = self.camera.read()
        self.shared_frame_mem: SharedMemory = SharedMemory(name='frame', size=self.frame.size*self.frame.itemsize, create=True)
        self.current_frame = numpy.ndarray(self.frame.shape, dtype=self.frame.dtype, buffer=self.shared_frame_mem.buf)
        self.initialization_lock.release()
        while self.benchmark:
            self.capture_image_benchmark()

        while not self.benchmark:
            self.capture_image()

    def capture_image(self):
        ret, frame = self.camera.read()
        numpy.copyto(self.current_frame, frame)
        #frame = resize_frame_relative(frame, 0.5)
        self.image_id += 1

    def capture_image_benchmark(self):
        numpy.copyto(self.current_frame, self.frame)
        self.image_id += 1


class WebSocketServer:
    def __init__(self, benchmark = False, id_camera: int = 0):
        self.frontend: WebSocketServerProtocol = None
        self.elvis: WebSocketServerProtocol = None
        self.camera = WebCam(benchmark, id_camera)
        self.fps = FPSCounter(2)
        self.trackers: dict[int, TrackerWrapper] = {}
        self.shared_frame_mem = None
        self.throttle_all = FPSCounter(FPS_120 / 5)

    async def start(self):
        async with  websockets.serve(self.accept_frontend, 'localhost', 5680):
            await Future()

    async def stream_video(self):
        sleep(1.5)
        self.camera.initialization_lock.acquire(blocking=True)
        self.shared_frame_mem = self.camera.shared_frame_mem # initialization
        while True:
            if not self.throttle_all.able_to_calculate():
                await asyncio.sleep(FPS_120 / 7)
                continue
            self.throttle_all.calculate()
            jpeg = CompressedImage.from_raw_image(self.camera.current_frame, self.camera.image_id,
                                                  quality=PREFER_PERFORMANCE_OVER_QUALITY)
            coordinates = [Coordinates(*tracker.coordinates_memory[:])
                           for tracker in self.trackers.values()]
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
                    tracker = TrackerWrapper(com_data.tracker_id, com_data.coords, self.shared_frame_mem)
                    self.trackers[com_data.tracker_id] = tracker
            await asyncio.sleep(FPS_120 * 2) # Throttle a bit cause the stream's priority is higher

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
    parser.add_argument('-i', '--id_camera',
                        type=int, default=0)
    args = parser.parse_args(sys.argv[1:])
    server = WebSocketServer(args.benchmark, args.id_camera)
    asyncio.run(server.start())
