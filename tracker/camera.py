from pathlib import Path
from datetime import datetime
from multiprocessing import Value
from multiprocessing.shared_memory import SharedMemory
from copy import copy

import cv2
import numpy

from tracker.utils.fps import FPSCounter, FPSLimiter
from tracker.utils.image_processing import rotate_frame
from tracker.utils.shared_objects import SharedFlag


class VideoAdapter:
    def __init__(self, frame: numpy.ndarray):
        # TODO: получает кадр и сам создает внутреннее представление данных по нему (shared memory и настройки кадра)
        self.shared_memory = SharedMemory(size=frame.size*frame.itemsize, create=True)
        self.height = frame.shape[0]
        self.width = frame.shape[1]
        self.rotate_degree = Value('i', 0)

    def setup_video_frame(self):
        self.video_frame = numpy.ndarray((self.height, self.width, 3), dtype=numpy.uint8, buffer=self.shared_memory.buf)

    def get_video_frame(self):
        return rotate_frame(self.video_frame, self.rotate_degree.value)

    def send_to_process(self):
        cp = copy(self)
        cp.video_frame = None
        return cp


def start_video_recording(filename, codec, fps, frame_size):
    fourcc = cv2.VideoWriter_fourcc(*codec)
    return cv2.VideoWriter(filename, fourcc, fps, frame_size)


def stream_video(camera: cv2.VideoCapture, video_adapter: VideoAdapter, recording: SharedFlag, source = 0, fps=120, resolution=640):
    codec = 'XVID'
    directory = 'video'
    recorder = None
    captured, frame = camera.read()
    if not captured:
        raise IOError("can't access camera")
    video_adapter.setup_video_frame()
    camera_fps = FPSCounter(1.5)
    fps_limit = FPSLimiter(fps)
    while True:
        if not fps_limit.able_to_execute():
            fps_limit.throttle()
        ret, frame = camera.read()
        try:
            numpy.copyto(video_adapter.video_frame, frame)
            if recording:
                if recorder is None:
                    # TODO: возможно для .exe надо будет тут костыль с путями делать
                    Path(directory).mkdir(exist_ok=True)
                    filename = f'{datetime.now().strftime("%d,%m,%Y_%H;%M;%S")}.avi'
                    full_path = str(Path(directory) / Path(filename))
                    recorder = start_video_recording(full_path, codec, fps, (video_adapter.width, video_adapter.height))
                recorder.write(frame)
            else:
                if recorder is not None:
                    recorder.release()
                    recorder = None


        except TypeError:
            # the video is over
            camera = cv2.VideoCapture(source)
        camera_fps.count_frame()
        if camera_fps.able_to_calculate():
            print(f'camera fps {camera_fps.calculate()}')
