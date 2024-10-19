from tkinter.messagebox import showerror
from multiprocessing import Process

import cv2
import numpy
import numpy as np

from eye_tracker.common.abstractions import Initializable
from eye_tracker.common.settings import settings, private_settings, FLIP_SIDE_NONE
from eye_tracker.view import view_output
from tracker.camera import VideoAdapter, stream_video
from tracker.utils.fps import FPSLimiter

DEGREE_TO_CV2_MAP = {
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE
}

DEFAULT_CAMERA_ID = 0


class NoneFrameException(Exception):
    ...


def stream_loop(video_adapter: VideoAdapter, source = 0, fps=120, resolution=640):
    video_adapter.setup_video_frame()

    fps_limit = FPSLimiter(fps)
    initialized = False

    while True:
        if not fps_limit.able_to_execute():
            fps_limit.throttle()
        if not initialized:
            camera = cv2.VideoCapture(source)
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, resolution)
            camera.set(cv2.CAP_PROP_FPS, fps)
            camera.set(cv2.CAP_PROP_BUFFERSIZE, 0)
            captured, frame = camera.read()

            if not captured:
                showerror(title='Ошибка', message='Не удалось получить изображение с камеры')
                raise IOError('Не удалось получить изображение с камеры')
            initialized = True
        captured, frame = camera.read()
        if not captured:
            raise IOError('Не удалось получить изображение с камеры')

        try:
            numpy.copyto(video_adapter.video_frame, frame)
        except TypeError:
            # the video is over
            initialized = False
            continue
        # camera_fps.count_frame()
        # if camera_fps.able_to_calculate():
        #     print(f'camera fps {camera_fps.calculate()}')


class CameraService(Initializable):
    def __init__(self, camera_id: int = settings.CAMERA_ID, auto_set=True):
        super().__init__(initialized=True)
        self._frame_rotate_degree = private_settings.ROTATION_ANGLE
        self._frame_flip_side = private_settings.FLIP_SIDE
        self.video_adapter: VideoAdapter = None
        if auto_set:
            self.set_source(camera_id)
            if not self.initialized:
                return
            self._camera.release()
            self.process = Process(target=stream_loop,
                                   args=(self.video_adapter, camera_id,
                                         settings.FPS_PROCESSED, settings.CAMERA_MAX_RESOLUTION,))
            self.process.start()

    def try_set_camera(self, camera_id):
        self._camera = cv2.VideoCapture(camera_id)
        self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, settings.CAMERA_MAX_RESOLUTION)
        #self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.CAMERA_MAX_RESOLUTION)
        self._camera.set(cv2.CAP_PROP_FPS, settings.FPS_PROCESSED)
        self._camera.set(cv2.CAP_PROP_BUFFERSIZE, 0)
        captured, frame = self._camera.read()
        if captured:
            self.video_adapter = VideoAdapter(frame)
            self.video_adapter.setup_video_frame()
        return self._camera.isOpened() and captured

    def set_source(self, source):
        if not self.try_set_camera(source):
            if not self.try_set_camera(DEFAULT_CAMERA_ID):
                self.init_error()
                view_output.show_error(
                    f'Не удалось открыть заданную настройкой CAMERA_ID камеру '
                    f'{source}, а так же не удалось определить подходящую камеру автоматически. '
                    f'Программа продолжит работать без контроллера камеры.'
                )
                self._camera = CameraStub()

    def set_frame_rotate(self, degree):
        if self.video_adapter:
            self.video_adapter.rotate_degree.value = degree

    def set_frame_flip(self, side):
        #self._frame_flip_side = side
        ...

    def rotate_frame(self, frame):
        degree = self._frame_rotate_degree
        if degree == 0:
            return frame
        else:
            return cv2.rotate(frame, DEGREE_TO_CV2_MAP[degree])

    def flip_frame(self, frame):
        side = self._frame_flip_side
        if side == FLIP_SIDE_NONE:
            return frame
        else:
            return cv2.flip(frame, side)

    def extract_frame(self):
        return numpy.copy(self.video_adapter.get_video_frame())
        # _, frame = self._camera.read()
        # if frame is None:
        #     raise NoneFrameException('Не удалось получить кадр с камеры')
        # rotated = self.rotate_frame(frame)
        # flipped = self.flip_frame(rotated)
        # # TODO: код ниже возможно мёртвый
        # if flipped is None:
        #     raise NoneFrameException('extracted frame is None after transformations')
        # return flipped


class CameraStub:

    def __init__(self):
        self._image = np.zeros((1, 1, 3), dtype=np.uint8)

    def set(self, param1, param2):
        pass

    def read(self):
        return None, self._image
