import cv2
import numpy as np

from common.abstractions import Initializable
from common.settings import settings, private_settings, FLIP_SIDE_NONE
from view import view_output

DEGREE_TO_CV2_MAP = {90: cv2.ROTATE_90_CLOCKWISE,
                     180: cv2.ROTATE_180,
                     270: cv2.ROTATE_90_COUNTERCLOCKWISE}

DEFAULT_CAMERA_ID = 0


class NoneFrameException(Exception):
    ...


class CameraService(Initializable):
    def __init__(self, source: int = settings.CAMERA_ID):
        super().__init__(initialized=True)
        self._frame_rotate_degree = private_settings.ROTATION_ANGLE
        self._frame_flip_side = private_settings.FLIP_SIDE
        self.set_source(source)

    def try_set_camera(self, camera_id):
        self._camera = cv2.VideoCapture(camera_id)
        self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, settings.CAMERA_MAX_HEIGHT_RESOLUTION)
        self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.CAMERA_MAX_HEIGHT_RESOLUTION)
        self._camera.set(cv2.CAP_PROP_FPS, settings.FPS_PROCESSED)
        self._camera.set(cv2.CAP_PROP_BUFFERSIZE, 0)
        return self._camera.isOpened()

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
        self._frame_rotate_degree = degree

    def set_frame_flip(self, side):
        self._frame_flip_side = side

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
        _, frame = self._camera.read()
        if frame is None:
            raise NoneFrameException('extracted frame is None with no reason')
        rotated = self.rotate_frame(frame)
        flipped = self.flip_frame(rotated)
        if flipped is None:
            raise NoneFrameException('extracted frame is None after transformations')
        return flipped


class CameraStub:

    def __init__(self):
        self._image = np.zeros((1, 1, 3), dtype=np.uint8)

    def set(self, param1, param2):
        pass

    def read(self):
        return None, self._image
