from multiprocessing import Process, Value
from multiprocessing.shared_memory import SharedMemory

import cv2
import numpy

from tracker.utils.fps import FPSCounter, FPSLimiter
from tracker.utils.image_processing import rotate_frame


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


def stream_video(video_adapter: VideoAdapter, source = 0, fps=120, resolution=640):
    camera = cv2.VideoCapture(source)
    camera.set(cv2.CAP_PROP_FPS, fps)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, resolution)
    video_adapter.setup_video_frame()
    camera_fps = FPSCounter()
    fps_limit = FPSLimiter(fps)
    while True:
        if not fps_limit.able_to_execute():
            fps_limit.throttle()
        ret, frame = camera.read()
        try:
            numpy.copyto(video_adapter.video_frame, frame)
        except TypeError:
            # the video is over
            camera = cv2.VideoCapture(source)
        camera_fps.count_frame()
        if camera_fps.able_to_calculate():
            print(f'camera fps {camera_fps.calculate()}')


def create_camera_streamer(id_camera = 0, fps=120, resolution=640) -> tuple[Process, VideoAdapter]:
    #image_id: ID = ID(0)
    # we can't serialize opencv object so we need to use functions
    camera = cv2.VideoCapture(id_camera)
    camera.set(cv2.CAP_PROP_FPS, fps)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, resolution)
    captured, frame = camera.read()
    if not captured:
        raise IOError("can't access camera")
    #camera.release()
    video_adapter = VideoAdapter(frame)
    process = Process(target=stream_video,
                      args=(video_adapter, id_camera, fps, resolution),
                      daemon=True)
    process.start()
    return process, video_adapter


