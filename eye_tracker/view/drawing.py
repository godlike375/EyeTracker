from typing import List, Tuple

import cv2
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans

from eye_tracker.common.coordinates import Point
from eye_tracker.common.logger import logger
from eye_tracker.common.settings import settings, private_settings, RESOLUTIONS, DOWNSCALED_WIDTH

SPLIT_PARTS = 4
BLUR_OPTIMAL_COEFFICIENT = 7
# другие значения не работают с 90 градусов поворотом при разрешениях кроме 640


class Processor:
    # white
    COLOR_NORMAL = (private_settings.PAINT_COLOR_R, private_settings.PAINT_COLOR_G, private_settings.PAINT_COLOR_B)
    COLOR_CAUTION = (0, 0, 255)
    THICKNESS = 2
    CURRENT_COLOR = COLOR_NORMAL
    FONT_SCALE = 0.8

    @staticmethod
    def frame_to_image(frame):
        if frame is None:
            logger.fatal('Frame is None type')
            raise Exception('Не удалось обработать кадр')
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb = Image.fromarray(rgb)
        return rgb

    @classmethod
    def draw_rectangle(cls, frame, left_top: Point, right_bottom: Point):
        left_top = left_top.to_int()
        right_bottom = right_bottom.to_int()
        # TODO: возможно понадобится более серьезная защита типа проверки на NAN и тд
        if left_top and right_bottom and left_top != right_bottom and left_top != Point(0, 0):
            return cv2.rectangle(frame, (*left_top,), (*right_bottom,), cls.CURRENT_COLOR, cls.THICKNESS)
        return frame

    @classmethod
    def draw_circle(cls, frame, center: Point):
        center = center.to_int()
        return cv2.circle(frame, (*center,), radius=cls.THICKNESS, color=cls.CURRENT_COLOR, thickness=cls.THICKNESS)

    @classmethod
    def draw_line(cls, frame, start: Point, end: Point):
        start = start.to_int()
        end = end.to_int()
        return cv2.line(frame, (*start,), (*end,), color=cls.CURRENT_COLOR, thickness=cls.THICKNESS)

    @classmethod
    def draw_text(cls, frame, text: str, coords: Point):
        font = cv2.FONT_HERSHEY_SIMPLEX
        return cv2.putText(frame, text, (coords.x, coords.y), font,
                           cls.FONT_SCALE, Processor.CURRENT_COLOR, cls.THICKNESS, cv2.LINE_AA)

    @staticmethod
    def resize_frame_relative(frame, percent):
        width = int(frame.shape[1] * percent)
        height = int(frame.shape[0] * percent)
        return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

    def resize_frame_absolute(frame, new_height, new_width):
        return cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)

    @classmethod
    def resize_to_minimum(cls, frame):
        frame_width = frame.shape[0]
        frame_height = frame.shape[1]
        if frame_height == DOWNSCALED_WIDTH or frame_width == DOWNSCALED_WIDTH:
            return frame
        reversed = frame_height < frame_width
        down_width = RESOLUTIONS[DOWNSCALED_WIDTH]
        if reversed:
            return cls.resize_frame_absolute(frame, DOWNSCALED_WIDTH, down_width)
        return cls.resize_frame_absolute(frame, down_width, DOWNSCALED_WIDTH)

    @classmethod
    def frames_are_same(cls, one, another):
        if one is None or another is None:
            return False
        if one.shape != another.shape:
            return False
        one = cls.resize_frame_relative(one, settings.DOWNSCALE_FACTOR)
        another = cls.resize_frame_relative(another, settings.DOWNSCALE_FACTOR)
        return all(i.mean() > settings.SAME_FRAMES_THRESHOLD for i in np.split((one == another), SPLIT_PARTS))

    @classmethod
    def load_color(cls):
        # TODO: возможно еще добавить выбор цвета предупреждения
        ps = private_settings
        color = (ps.PAINT_COLOR_B, ps.PAINT_COLOR_G, ps.PAINT_COLOR_R)
        cls.COLOR_NORMAL = color
        cls.CURRENT_COLOR = color

    @staticmethod
    def cluster_pixels(image, num_clusters=2):
        # Преобразование изображения в двумерный массив пикселей
        pixels = np.reshape(image, (-1, 3))

        # Кластеризация пикселей по цвету
        kmeans = KMeans(n_clusters=num_clusters)
        kmeans.fit(pixels)
        labels = kmeans.predict(pixels)

        # Создание маски для каждого кластера
        masks = []
        labels = np.reshape(labels, (image.shape[0], image.shape[1]))
        labels = np.stack([labels, labels, labels], axis=2)
        for i in range(num_clusters):
            mask = np.zeros_like(image)
            mask[np.where(labels == i)] = image[np.where(labels == i)]
            masks.append(mask)

        return masks

    @staticmethod
    def get_biggest_mask(masks: List[np.ndarray]):
        biggest_mask = masks[0]
        biggest_size = 0
        for mask in masks:
            current = np.concatenate(mask).sum()
            if current > biggest_size:
                biggest_mask = mask
                biggest_size = current

        return biggest_mask

    @staticmethod
    def get_color_ranges(mask: np.ndarray):
        transposed = np.transpose(mask)
        split_channels = [i for i in transposed]
        color_min_max = []
        for channel in split_channels:
            min_value = np.min(channel[channel != 0], axis=0)
            max_value = np.max(channel[channel != 0], axis=0)
            color_min_max.append((min_value, max_value,))
        lower, upper = [i for i in np.array(color_min_max).transpose()]
        return lower, upper

    @staticmethod
    def blur_image(image):
        return cv2.blur(image, (BLUR_OPTIMAL_COEFFICIENT, BLUR_OPTIMAL_COEFFICIENT))

    @staticmethod
    def paint_zero_pixels(image: np.ndarray, new_color: Tuple[int, int, int]):
        image[np.where((image == [0, 0, 0]).all(axis=2))] = new_color

    @staticmethod
    def paint_laser_black(image: np.ndarray, lower, upper):
        masked_image = cv2.bitwise_not(cv2.inRange(image, lower, upper))
        return cv2.bitwise_and(image, image, mask=masked_image)

    @staticmethod
    def replace_hsv_range(hsv_img, h_min, h_max, new_h):
        mask = cv2.inRange(hsv_img, (h_min, 0, 0), (h_max, 255, 255))
        # Создание массива с той же формой, что и hsv_image
        new_hsv = np.zeros_like(hsv_img)

        # Замена значений H в маске на новое значение
        #new_hsv[:, :, 0] = np.where(mask > 0, new_h, hsv_img[:, :, 0])
        new_hsv[:, :, 2] = np.where(mask > 0, 30, hsv_img[:, :, 2])

        # Копирование значений S и V из hsv_image
        new_hsv[:, :, 1] = hsv_img[:, :, 1]
        return new_hsv

    @staticmethod
    def bgr_to_hsv(image: np.ndarray):
        return cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    @staticmethod
    def hsv_to_bgr(image: np.ndarray):
        return cv2.cvtColor(image, cv2.COLOR_HSV2BGR)