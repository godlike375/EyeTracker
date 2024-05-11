import asyncio
import sys
from asyncio import Future

import websockets

from websockets import WebSocketServerProtocol

sys.path.append('..')

from tracker.image import CompressedImage, PREFER_PERFORMANCE_OVER_QUALITY
from tracker.protocol import Command, Commands, Coordinates, ImageWithCoordinates, StartTracking
from tracker.fps_counter import FPSCounter
from tracker.object_tracker import TrackerWrapper, FPS_120
from time import sleep


class GazePredictorBackend:
    def __init__(self):
        self.frontend: WebSocketServerProtocol = None
        self.elvis: WebSocketServerProtocol = None
        self.fps = FPSCounter(2)
        self.shared_frame_mem = None
        self.throttle_all = FPSCounter(FPS_120 / 5)
        asyncio.run(self.start())

    async def start(self):
        async with websockets.serve(self.on_new_connection, 'localhost', 5680):
            await Future()

    async def stream_video(self):
        sleep(1.5)
        self.camera.initialization_lock.acquire(blocking=True)
        self.shared_frame_mem = self.camera.video_frame # initialization
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


    async def receive_messages(self, elvis: WebSocketServerProtocol):
        while True:
            msg = await elvis.recv()
            command = Command.unpack(msg)
            # match command.type:
            #     case Commands.START_TRACKING:
            #         com_data: StartTracking = command.data
            await asyncio.sleep(FPS_120 * 2) # Throttle a bit cause the stream's priority is higher

    async def on_new_connection(self, elvis: WebSocketServerProtocol, path):
        try:
            await self.receive_messages(elvis)
        except websockets.exceptions.ConnectionClosed:
            # TODO: unregister elvis
            print('Elvis client disconnected')