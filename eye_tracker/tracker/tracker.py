import dataclasses
import queue
import time
from multiprocessing import Process, Queue

import dlib

from eye_tracker.tracker.fps_counter import FPSCounter
from eye_tracker.tracker.image import CompressedImage
from eye_tracker.tracker.protocol import Coordinates
from eye_tracker.tracker.abstractions import ID


class TrackerWrapper:
    def __init__(self, id: int, coordinates: Coordinates):
        self.id = id
        self.video_stream = Queue(maxsize=2)
        self.coordinates_commands_stream = Queue(maxsize=2)
        self.process = Process(
                target=self._mainloop,
                args=(self.video_stream, self.coordinates_commands_stream, id, coordinates),
                daemon=True
            )
        self.process.start()

    def _mainloop(self, video_stream: Queue, coordinates_commands: Queue,
                  id: ID, coordinates: Coordinates):
        fps = FPSCounter()
        print(f'tracker start id {id}')
        started = False
        stopped = False
        tracker = dlib.correlation_tracker()
        while not stopped:
            while True:
                try:
                    frame_bytes = video_stream.get_nowait()
                    break
                except queue.Empty:
                    time.sleep(0.0065)
            image = CompressedImage.unpack(frame_bytes)
            raw = image.to_raw_image()

            if not started:
                started = True
                tracker.start_track(raw, dlib.rectangle(*dataclasses.astuple(coordinates)))
            tracker.update(raw)
            new_pos = tracker.get_position()
            new_coordinates = new_pos.left(), new_pos.top(), new_pos.right(), new_pos.bottom()
            fps.count_frame()
            if fps.able_to_calculate():
                print(fps.calculate())
                print(f'update tracker id {id} coordinates {new_coordinates}')

            while True:
                try:
                    coordinates_commands.put_nowait(Coordinates(*new_coordinates))
                    break
                except queue.Full:
                    time.sleep(0.0065)
