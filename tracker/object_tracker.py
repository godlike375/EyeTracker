import dataclasses
from collections import deque
from multiprocessing import Process, JoinableQueue
from time import sleep

import dlib

from tracker.fps_counter import FPSCounter
from tracker.image import CompressedImage
from tracker.protocol import Coordinates, FrameTrackerCoordinates
from tracker.abstractions import ID, try_few_times


FPS_120 = 1 / 900
MAX_LATENCY = 2


class TrackerWrapper:
    def __init__(self, id: ID, coordinates: Coordinates):
        self.id = id
        self.video_stream = JoinableQueue(maxsize=1)
        self.coordinates_commands_stream = JoinableQueue(maxsize=1)
        self.process = Process(
                target=self._mainloop,
                args=(self.video_stream, self.coordinates_commands_stream, id, coordinates),
                daemon=True
            )
        self.process.start()

    def _mainloop(self, video_stream: JoinableQueue, coordinates_commands: JoinableQueue,
                  id: ID, coordinates: Coordinates):
        fps = FPSCounter(2)
        print(f'tracker start id {id}')
        started = False
        stopped = False
        tracker = dlib.correlation_tracker()
        while not stopped:
            image: CompressedImage = video_stream.get()
            #print(f'get frame {image.id}')
            raw = image.to_raw_image()

            if not started:
                started = True
                tracker.start_track(raw, dlib.rectangle(*dataclasses.astuple(coordinates)))
            tracker.update(raw)
            new_pos = tracker.get_position()
            new_coordinates = new_pos.left(), new_pos.top(), new_pos.right(), new_pos.bottom()
            fps.count_frame()
            if fps.able_to_calculate():
                print(f'tracker fps: {fps.calculate()}')
            result = FrameTrackerCoordinates(image.id, id, Coordinates(*new_coordinates))
            coordinates_commands.put(result)
            #print(f'put frame {image.id}')