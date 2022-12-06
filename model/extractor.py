import cv2

from common.settings import Settings


class Extractor():
    def __init__(self, source: int):
        self.set_source(source)

    def set_source(self, source):
        self._camera = cv2.VideoCapture(source)
        self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, Settings.CAMERA_MAX_RESOLUTION)
        self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, Settings.CAMERA_MAX_RESOLUTION)
        self._camera.set(cv2.CAP_PROP_FPS, Settings.FPS)
        if not self._camera.isOpened():
            raise RuntimeError('Неверный ID камеры')

    def extract_frame(self):
        _, frame = self._camera.read()
        return frame
