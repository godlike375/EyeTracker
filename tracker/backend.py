import argparse
import asyncio
import multiprocessing
import sys
from asyncio import Future
from collections import defaultdict
from dataclasses import dataclass
from threading import Thread
from queue import Queue

import websockets

import cv2
from websockets import WebSocketServerProtocol

sys.path.append('..')

from tracker.image import CompressedImage, PREFER_PERFORMANCE_OVER_QUALITY, resize_frame_relative
from tracker.protocol import Command, Commands, ImageWithCoordinates, StartTracking, FrameTrackerCoordinates
from tracker.abstractions import ID, MutableVar, try_one_time
from tracker.fps_counter import FPSCounter
from tracker.object_tracker import TrackerWrapper, FPS_120, MAX_LATENCY


class WebCam:
    def __init__(self, benchmark = False):
        self.image_id: ID = ID(0)

        self.frames = Queue(maxsize=MAX_LATENCY)
        self.thread = Thread(target=self.mainloop, daemon=True)
        self.thread.start()
        self.benchmark = benchmark

    def mainloop(self):
        self.camera = cv2.VideoCapture(0)
        self.camera.set(cv2.CAP_PROP_FPS, 60)
        if self.benchmark:
            self.ret, self.frame = self.camera.read()
            #self.frame = resize_frame_relative(self.frame, 0.625)
            while True:
                self.frames.put(self.capture_image_benchmark())
        else:
            while True:
                self.frames.put(self.capture_image())

    def __del__(self):
        self.camera.release()

    def capture_image(self) -> CompressedImage:
        ret, frame = self.camera.read()
        #frame = resize_frame_relative(frame, 0.625)
        jpeg = CompressedImage.from_raw_image(frame, self.image_id, quality=PREFER_PERFORMANCE_OVER_QUALITY)
        self.image_id += 1
        return jpeg if ret else None

    def capture_image_benchmark(self) -> CompressedImage:
        jpeg = CompressedImage.from_raw_image(self.frame, self.image_id, quality=PREFER_PERFORMANCE_OVER_QUALITY)
        self.image_id += 1
        return jpeg if self.ret else None


@dataclass
class TrackerState:
    processing_frame_id: ID
    ready: bool


class WebSocketServer:
    def __init__(self, benchmark = False):
        self.frontend: WebSocketServerProtocol = None
        self.elvis: WebSocketServerProtocol = None
        self.camera = WebCam(benchmark)
        self.fps = FPSCounter(2)
        self.trackers: dict[int, TrackerWrapper] = {}
        self.processed_frames: defaultdict[ID, ImageWithCoordinates] = defaultdict(ImageWithCoordinates)
        self.ready_frames = asyncio.Queue(maxsize=MAX_LATENCY)
        self.trackes_states: dict[ID, TrackerState] = {}

    async def start(self):
        async with websockets.serve(self.accept_frontend, 'localhost', 5680):
            await Future()

    def check_frame_ready(self, frame_id: ID):
        if len(self.processed_frames[frame_id].trackers_coords) == len(self.trackers):
            frame = self.processed_frames[frame_id]
            del self.processed_frames[frame_id]
            #self.ready_frames.put(frame)
            self.ready_frames.put_nowait(frame)

    def build_frame(self, coordinates: FrameTrackerCoordinates, tracker_id: ID):
        frame_id = coordinates.frame_id
        if frame_id in self.processed_frames:
            frame_coordinates = self.processed_frames[frame_id].trackers_coords
            frame_coordinates[tracker_id] = coordinates.coords
            self.check_frame_ready(frame_id)

    def _wait_for_tracker_process_result(self, tracker: TrackerWrapper):
        coordinates: FrameTrackerCoordinates = tracker.coordinates_commands_stream.get()
        #print(f'received late {coordinates.frame_id}')
        self.trackes_states[tracker.id].ready = True
        self.build_frame(coordinates, tracker.id)

    async def receive_from_late_trackers(self):
        #print('late')
        oldest_frame_id: ID = min(self.processed_frames.keys())
        late_trackers_ids = [tracker_id for tracker_id, state in self.trackes_states.items()
                             if state.processing_frame_id == oldest_frame_id and not state.ready]
        wait_tasks = [asyncio.to_thread(self._wait_for_tracker_process_result, self.trackers[id])
                      for id in late_trackers_ids]
        # we can get result like results = await asyncio.gather(*wait_tasks)
        await asyncio.gather(*wait_tasks)

    async def get_frames_wait_late_trackers(self):
        while True:
            if self.trackers and len(self.processed_frames) == MAX_LATENCY:
                await self.receive_from_late_trackers()

            try:
                jpeg = self.camera.frames.get_nowait()
                if not self.trackers:
                    await self.ready_frames.put(ImageWithCoordinates(jpeg))
                if self.trackers and len(self.processed_frames) < MAX_LATENCY:
                    self.processed_frames[jpeg.id] = ImageWithCoordinates(jpeg)

            except:
                ...

            if self.fps.able_to_calculate():
                print(f'backend fps: {self.fps.calculate()}')
                print(f'{self.processed_frames.keys()}')
            self.fps.count_frame()

            # TODO: адаптивный sleep (если и так долго цикл длился, то спать меньше)
            await asyncio.sleep(FPS_120)


    def receive_from_trackers_nonblock(self):
        for t in self.trackers.values():
            res = MutableVar()
            if try_one_time(lambda : res.set(t.coordinates_commands_stream.get_nowait())):
                self.trackes_states[t.id].ready = True
                coordinates: FrameTrackerCoordinates = res.value
                #print(f'received early {coordinates.frame_id}')
                self.build_frame(coordinates, t.id)


    def send_to_trackers_no_block(self):
        ready_trackers_ids = [tracker_id for tracker_id, state in self.trackes_states.items()
                             if state.ready]
        if not self.processed_frames:
            return
        for id in ready_trackers_ids:
            try:
                next_frame_id = min(frame_id for frame_id in self.processed_frames.keys()
                                   if frame_id > self.trackes_states[id].processing_frame_id)
            except:
                # no new frame for ready tracker cause it already processed the most recent one
                continue

            self.trackes_states[id].processing_frame_id = next_frame_id
            next_frame = self.processed_frames[next_frame_id]
            # Из нашей схемы мы точно знаем, что трекер сейчас ожидает задачу
            self.trackers[id].video_stream.put_nowait(next_frame.image)
            #print(f'send {next_frame.image.id}')
            self.trackes_states[id].ready = False


    async def receive_send_trackers_nonblock(self):
        while True:
            #if self.trackers and len(self.processed_frames) < MAX_LATENCY:
            self.receive_from_trackers_nonblock()

            self.send_to_trackers_no_block()
            self.fps.count_frame()
            # TODO: адаптивный sleep (если и так долго цикл длился, то спать меньше)
            await asyncio.sleep(FPS_120)

    async def receive_frontend_commands(self):
        while True:
            cmd_msg = await self.frontend.recv()
            command = Command.unpack(cmd_msg)
            match command.type:
                case Commands.START_TRACKING:
                    com_data: StartTracking = command.data
                    tracker = TrackerWrapper(com_data.tracker_id, com_data.coords)
                    await asyncio.sleep(1.5)
                    self.trackers[com_data.tracker_id] = tracker
                    self.trackes_states[com_data.tracker_id] = TrackerState(0, True)
            await asyncio.sleep(FPS_120 * 10) # Throttle a bit cause the stream's priority is higher

    async def send_video_to_frontend(self):
        while True:
            frame = await self.ready_frames.get()
            await self.frontend.send(frame.pack())

    async def accept_frontend(self, websocket: WebSocketServerProtocol, path):
        name = await websocket.recv()
        match name:
            case 'frontend':
                self.frontend = websocket
            case 'elvis':
                self.elvis = websocket

        try:
            await asyncio.gather(
                self.receive_frontend_commands(),
                self.receive_send_trackers_nonblock(),
                self.get_frames_wait_late_trackers(),
                self.send_video_to_frontend()
                )
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
