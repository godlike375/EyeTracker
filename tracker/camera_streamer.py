from multiprocessing import Process
from multiprocessing.shared_memory import SharedMemory

import cv2
import numpy

from tracker.utils.fps import FPSCounter


def stream_video(shared_frame_mem: SharedMemory, id_camera = 0, fps=120, resolution=640):
    camera = cv2.VideoCapture(id_camera)
    camera.set(cv2.CAP_PROP_FPS, fps)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, resolution)
    ret, frame = camera.read()
    current_frame = numpy.ndarray(frame.shape, dtype=frame.dtype, buffer=shared_frame_mem.buf)
    camera_fps = FPSCounter()
    while True:
        ret, frame = camera.read()
        numpy.copyto(current_frame, frame)
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
    shared_frame_mem: SharedMemory = SharedMemory(name='frame', size=frame.size*frame.itemsize, create=True)
    process = Process(target=stream_video, args=(shared_frame_mem, id_camera, fps, resolution), daemon=True)
    process.start()
    current_frame = numpy.ndarray(frame.shape, dtype=frame.dtype, buffer=shared_frame_mem.buf)
    return current_frame, process, shared_frame_mem


