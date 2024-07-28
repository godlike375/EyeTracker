import dataclasses
from multiprocessing import Process, Array, RawValue
from multiprocessing.shared_memory import SharedMemory

import dlib
import numpy

from tracker.utils.fps import FPSCounter
from tracker.utils.coordinates import BoundingBox
from tracker.abstractions import ID


class TrackerWrapper:
    def __init__(self, id: int, coordinates: BoundingBox, frame_memory: SharedMemory):
        self.id = id
        self.frame_memory = frame_memory
        self.coordinates_memory = Array('i', [0] * 4)
        self.stopped = RawValue('i', 0)
        self.process = Process(
                target=self._mainloop,
                args=(self.coordinates_memory, id, coordinates),
                daemon=True
            )
        self.process.start()

    def _mainloop(self, coordinates_memory: Array,
                  id: ID, coordinates: BoundingBox):
        fps = FPSCounter(2)
        print(f'tracker start id {id}')
        started = False
        tracker = dlib.correlation_tracker()
        raw = numpy.ndarray((480, 640, 3), dtype=numpy.uint8, buffer=self.frame_memory.buf)
        while True:
            if self.stopped.value:
                exit()
            if not started:
                started = True
                tracker.start_track(raw, dlib.rectangle(*dataclasses.astuple(coordinates)))
            confidence = tracker.update(raw)
            if confidence < 4.65:
                print(f'object lost {confidence}')
            new_pos = tracker.get_position()
            coordinates_memory[0] = int(new_pos.left())
            coordinates_memory[1] = int(new_pos.top())
            coordinates_memory[2] = int(new_pos.right())
            coordinates_memory[3] = int(new_pos.bottom())
            fps.count_frame()
            if fps.able_to_calculate():
                print(f'tracker fps: {fps.calculate()}')