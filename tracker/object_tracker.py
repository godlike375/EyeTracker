import dataclasses
from multiprocessing import Process, Queue

import dlib

from tracker.fps_counter import FPSCounter
from tracker.image import CompressedImage
from tracker.protocol import Coordinates
from tracker.abstractions import ID, try_few_times


FPS_120 = 1 / 120


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
        fps = FPSCounter(2)
        print(f'tracker start id {id}')
        started = False
        stopped = False
        tracker = dlib.correlation_tracker()
        while not stopped:
            image = CompressedImage.unpack(video_stream.get())
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
            coordinates_commands.put(Coordinates(*new_coordinates))