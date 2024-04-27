import dataclasses
from multiprocessing import Process, Array
from multiprocessing.shared_memory import SharedMemory

import dlib
import numpy

from tracker.fps_counter import FPSCounter
from tracker.protocol import Coordinates
from tracker.abstractions import ID


FPS_120 = 1 / 120


class TrackerWrapper:
    def __init__(self, id: int, coordinates: Coordinates, frame_memory: SharedMemory):
        self.id = id
        self.frame_memory = frame_memory
        self.coordinates_memory = Array('i', [0] * 4)
        self.process = Process(
                target=self._mainloop,
                args=(self.frame_memory, self.coordinates_memory, id, coordinates),
                daemon=True
            )
        self.process.start()

    def _mainloop(self, frame_memory: SharedMemory, coordinates_memory: Array,
                  id: ID, coordinates: Coordinates):
        fps = FPSCounter(2)
        print(f'tracker start id {id}')
        started = False
        tracker = dlib.correlation_tracker()
        raw = numpy.ndarray((480, 640, 3), dtype=numpy.uint8, buffer=self.frame_memory.buf)
        while True:
            if not started:
                started = True
                tracker.start_track(raw, dlib.rectangle(*dataclasses.astuple(coordinates)))
            tracker.update(raw)
            new_pos = tracker.get_position()
            coordinates_memory[0] = int(new_pos.left())
            coordinates_memory[1] = int(new_pos.top())
            coordinates_memory[2] = int(new_pos.right())
            coordinates_memory[3] = int(new_pos.bottom())
            fps.count_frame()
            if fps.able_to_calculate():
                print(f'tracker fps: {fps.calculate()}')