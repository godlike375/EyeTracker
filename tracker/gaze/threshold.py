import cv2
import numpy
import numpy as np

threshold = 0

def update_threshold(val):
    global threshold
    threshold = val

cv2.namedWindow("Thresholded Image")
cv2.createTrackbar("Threshold", "Thresholded Image", 0, 255, update_threshold)

cap = cv2.VideoCapture(1)  # Открываем веб-камеру


def remove_zeroes_and_take_percentile(hist, percent):
    pairs = [(i, int(hist[i][0])) for i in range(len(hist))]
    pairs.sort(key=lambda x: x[1])
    pairs = [(i, v) for (i, v) in pairs if v > 0]
    percentile_25th = int(len(pairs) * percent / 100)
    return pairs[percentile_25th:]


def find_optimal_threshold(blurred, base_factor=None):
    hist = cv2.calcHist([blurred], [0], None, [256], [0, 256])
    # the coefficients are optimal in most scenarios
    sorted_by_values = remove_zeroes_and_take_percentile(hist, percent=5.03)
    sorted_by_indexes = sorted(sorted_by_values, key=lambda x: x[0])
    min_val = max(sorted_by_indexes[0][0], 1)
    max_val = max(sorted_by_indexes[-1][0], 2)
    # the coefficients are optimal in most scenarios

    # base_factor = base_factor or ((max_val - min_val) ** 1.65 / 255 ** 1.65) + 0.6
    # base_factor = max(base_factor, 1.07)

    base_factor = base_factor or ((max_val - min_val) ** 1.18 / 255 ** 1.18) ** 1.1 + 0.71
    base_factor = max(base_factor, 1.078)

    # latest
    # base_factor = base_factor or ((max_val - min_val) ** 1.5 / 255 ** 1.5) + 0.45
    # base_factor = max(base_factor, 1.085)

    # base_factor = base_factor or ((max_val - min_val) / 255) ** 1.11 + 0.5
    # base_factor = max(base_factor, 1.038)
    try_threshold = int(min_val * base_factor)
    return try_threshold


def blur_image(gray: numpy.ndarray, blur=0, dilate=0, erode=0):
    blurred = gray
    if blur:
        blurred = cv2.medianBlur(blurred, blur)
    if dilate:
        kernel = np.ones((dilate, dilate), np.uint8)
        blurred = cv2.dilate(blurred, kernel, iterations=1)
    if erode:
        kernel = np.ones((erode, erode), np.uint8)
        blurred = cv2.erode(blurred, kernel, iterations=1)
    return blurred

def contrast_image(frame: numpy.ndarray, contrast=1.3, brightness = 0):
    return cv2.addWeighted(frame, contrast, numpy.zeros(frame.shape, frame.dtype), 0, brightness)


while True:
    ret, frame = cap.read()  # Читаем кадр с веб-камеры

    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # Переводим в оттенки серого
    blurred = gray
    #blurred = contrast_image(blurred, contrast=1.61)

    # and also not bad
    # blurred = blur_image(blurred, blur=5, erode=3)

    # also not bad
    # blurred = blur_image(blurred, blur=7)
    # blurred = blur_image(blurred, blur=1, erode=3)
    # blurred = blur_image(blurred, blur=5)
    # blurred = blur_image(blurred, blur=1, erode=2)

    blurred = blur_image(blurred, blur=7)
    blurred = blur_image(blurred, blur=3)
    blurred = blur_image(blurred, dilate=3)
    blurred = blur_image(blurred, erode=2)
    #blurred = blur_image(blurred, blur=3)
    #blurred = blur_image(blurred, erode=2)

    #blurred = blur_image(blurred, blur=3)

    # not bad
    # blurred = blur_image(blurred, blur=5)
    # blurred = blur_image(blurred, blur=1, erode=4)
    # blurred = blur_image(blurred, blur=3)

    #print(find_optimal_threshold(blurred))
    _, thresholded = cv2.threshold(blurred, threshold, 255, cv2.THRESH_BINARY)  # Применяем пороговое преобразование

    cv2.imshow("Thresholded Image", blurred)  # Отображаем thresholded изображение
    cv2.imshow("Thresholded Image2", thresholded)
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
