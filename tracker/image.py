from datetime import datetime
import io
from dataclasses import dataclass

import PIL
import cv2
from PIL.Image import Image
import numpy

from tracker.abstractions import ID
from tracker.protocol import Packable

PREFER_PERFORMANCE_OVER_QUALITY = 35
MSEC_IN_SEC = 1000


# works 2 times faster than imencode!
def encode_array_to_jpeg(image: Image, quality=PREFER_PERFORMANCE_OVER_QUALITY) -> bytes:
    with io.BytesIO() as output_buffer:
        image.save(output_buffer, format='JPEG', quality=quality)  # Сохраняем изображение в буфер в формате JPEG
        return output_buffer.getvalue()


# works a 10% faster than imdecode
def decode_jpeg_to_array(jpeg_data: bytes) -> numpy.ndarray:
    with io.BytesIO(jpeg_data) as input_buffer:
        decoded_image = PIL.Image.open(input_buffer, formats=('JPEG',))  # Открываем изображение из буфера
        decoded_image = decoded_image.convert("RGB")  # Преобразуем в RGB, если это необходимо
    return numpy.asarray(decoded_image)


@dataclass(slots=True, frozen=True)
class CompressedImage(Packable):
    id: ID
    jpeg_bytes: bytes
    timestamp: int # milliseconds from 01.01.1970

    def to_raw_image(self) -> numpy.ndarray:
        return decode_jpeg_to_array(self.jpeg_bytes)

    @classmethod
    def from_raw_image(cls, raw: numpy.ndarray, id: ID, quality=35) -> 'CompressedImage':
        img = PIL.Image.fromarray(raw)
        return CompressedImage(id,
                               encode_array_to_jpeg(img, quality=quality),
                               int(datetime.timestamp(datetime.now()) * MSEC_IN_SEC))


def resize_frame_relative(frame: numpy.ndarray, percent):
    width = int(frame.shape[1] * percent)
    height = int(frame.shape[0] * percent)
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
