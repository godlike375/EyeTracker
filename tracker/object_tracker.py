import dataclasses
from multiprocessing import Process, Queue

import dlib

from tracker.fps_counter import FPSCounter
from tracker.image import CompressedImage
from tracker.network import InputBuffer, OutputBuffer, BufferPoller
from tracker.protocol import Coordinates
from tracker.abstractions import ID, try_few_times, MutableVar

FPS_120 = 1 / 120


class TrackerWrapper:
    def __init__(self, id: int, coordinates: Coordinates):
        self.id = id
        self.video_stream = Queue(maxsize=2)
        self.video_buffer = OutputBuffer(self.video_stream)

        self.coordinates_commands_stream = Queue(maxsize=2)
        self.coordinates_commands_buffer = InputBuffer(self.coordinates_commands_stream)
        self.process = Process(
                target=tracker_mainloop,
                args=(self.video_stream, self.coordinates_commands_stream, id, coordinates),
                daemon=True
            )
        self.process.start()

def tracker_mainloop(video_stream: Queue, coordinates_stream: Queue,
              id: ID, coordinates: Coordinates):

    video_buffer = InputBuffer(video_stream)
    coordinates_buffer = OutputBuffer(coordinates_stream)
    buffer_pooler = BufferPoller([video_buffer, coordinates_buffer])

    fps = FPSCounter(2.5)
    print(f'tracker start id {id}')
    started = False
    stopped = False
    tracker = dlib.correlation_tracker()
    frame = MutableVar()
    while not stopped:
        try_few_times(lambda: frame.set(video_buffer.get_nowait()),
                      interval=FPS_120 / 3, times=4)
        if not frame.value:
            continue
        image = CompressedImage.unpack(frame.value)
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

        try_few_times(lambda : coordinates_buffer.put_nowait(Coordinates(*new_coordinates)),
                      interval=FPS_120 / 2)