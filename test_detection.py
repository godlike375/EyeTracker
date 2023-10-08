from typing import List

import numpy as np
from sklearn.cluster import KMeans
import cv2


def cluster_pixels(image, num_clusters):
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

def get_biggest_mask(masks: List[np.ndarray]):
    biggest_mask = masks[0]
    biggest_size = 0
    for mask in masks:
        current = np.concatenate(mask).sum()
        print(current)
        if current > biggest_size:
            biggest_mask = mask
            biggest_size = current

    return biggest_mask

def get_color_ranges(mask: np.ndarray):
    transposed = np.transpose(mask)
    split_channels = [i for i in transposed]
    color_min_max = []
    for channel in split_channels:
        min_value = np.min(channel[channel != 0], axis=0)
        max_value = np.max(channel[channel != 0], axis=0)
        color_min_max.append((min_value, max_value,))
    return color_min_max

# Загрузка изображения
image = cv2.imread('example_image.jpg')

# Кластеризация пикселей изображения
num_clusters = 2
masks = cluster_pixels(image, num_clusters)
mask = get_biggest_mask(masks)
ranges = get_color_ranges(mask)
lower, upper = [i for i in np.array(ranges).transpose()]

masked_image = cv2.bitwise_not(cv2.inRange(image, lower, upper))

# Применяем маску к изображению
result = cv2.bitwise_and(image, image, mask=masked_image)

new_color = (255, 0, 0)
result[np.where((result == [0, 0, 0]).all(axis=2))] = new_color

cv2.imshow(f'Biggest', result)

# Вывод кластеров объектов различных форм и цветов
#for i, mask in enumerate(masks):
#    cv2.imshow(f'Cluster {i}', mask)

cv2.imshow(f'Cluster', image)

cv2.waitKey(0)
cv2.destroyAllWindows()