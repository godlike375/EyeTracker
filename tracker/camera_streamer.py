from multiprocessing import Process
from multiprocessing.shared_memory import SharedMemory

import cv2
import numpy

from tracker.utils.fps import FPSCounter, FPSLimiter


def stream_video(shared_frame_mem: SharedMemory, source = 0, fps=120, resolution=640):
    camera = cv2.VideoCapture(source)
    camera.set(cv2.CAP_PROP_FPS, fps)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, resolution)
    ret, frame = camera.read()
    current_frame = numpy.ndarray(frame.shape, dtype=frame.dtype, buffer=shared_frame_mem.buf)
    camera_fps = FPSCounter()
    fps_limit = FPSLimiter(fps)
    while True:
        if not fps_limit.able_to_execute():
            fps_limit.throttle()
        ret, frame = camera.read()
        try:
            numpy.copyto(current_frame, frame)
        except TypeError:
            # the video is over
            camera = cv2.VideoCapture(source)
        camera_fps.count_frame()
        if camera_fps.able_to_calculate():
            print(f'camera fps {camera_fps.calculate()}')


def create_camera_streamer(id_camera = 0, fps=120, resolution=640):
    #image_id: ID = ID(0)
    # we can't serialize opencv object so we need to use functions
    camera = cv2.VideoCapture(id_camera)
    camera.set(cv2.CAP_PROP_FPS, fps)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, resolution)
    captured, frame = camera.read()
    if not captured:
        raise IOError("can't access camera")
    camera.release()
    shared_frame_mem: SharedMemory = SharedMemory(size=frame.size*frame.itemsize, create=True)
    process = Process(target=stream_video, args=(shared_frame_mem, id_camera, fps, resolution), daemon=True)
    process.start()
    current_frame = numpy.ndarray(frame.shape, dtype=frame.dtype, buffer=shared_frame_mem.buf)
    return current_frame, process, shared_frame_mem


