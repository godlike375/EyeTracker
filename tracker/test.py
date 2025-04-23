import cv2
import numpy as np

import numpy as np
from scipy.spatial.distance import euclidean

from fastdtw import fastdtw
from scipy.stats import linregress

x = np.array([[1,1], [2,2], [3,3]])
y = np.array([[3,3], [2,2], [1,1]])
distance, path = fastdtw(x, y, dist=euclidean)
print(path)

x = np.array([1, 1, 2, 1, 2, 3, 4, 1])
y = np.array([1, 1, 2, 1, 2, 3, 4, 2])

slope, intercept, r_value, p_value, std_err = linregress(x, y)
r_squared = r_value ** 2
consistent_direction = r_squared > 0.3
print(r_squared)



class AveragedFrameBuffer:
    def __init__(self, frame_count):
        self.frame_count = frame_count
        self.frames = []
        self.current_index = 0
        self.is_full = False

    def add_frame(self, frame):
        # Проверка размера кадра (чтобы избежать проблем с размером)
        if not self.frames:
            self.frames.append(frame)
        else:
            if frame.shape != self.frames[0].shape:
                raise ValueError("Frame shape must match the shape of existing frames")

        # Добавление кадра в буфер
        if self.is_full:
            self.frames[self.current_index] = frame
        else:
            self.frames.append(frame)
            if len(self.frames) == self.frame_count:
                self.is_full = True

        self.current_index = (self.current_index + 1) % self.frame_count

    def get_average_frame(self):
        if not self.frames:
            raise ValueError("No frames to average")

        average_frame = np.mean(self.frames, axis=0).astype(np.uint8)
        return average_frame


cap = cv2.VideoCapture(0)

fgbg = cv2.createBackgroundSubtractorKNN(history=245, dist2Threshold=23, detectShadows=False)
fgbg.setNSamples(3)
#fgbg.setComplexityReductionThreshold(0.008)
#fgbg.setVarThresholdGen(0.05)
masks = AveragedFrameBuffer(6)
frames = AveragedFrameBuffer(6)



while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # Применение метода вычитания фона
    frame = cv2.resize(frame, (320, 240))

    frame = cv2.medianBlur(frame, 3)
    frames.add_frame(np.copy(frame))
    avg = frames.get_average_frame()

    thresholded = cv2.threshold(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), 238, 255, cv2.THRESH_BINARY)
    cv2.imshow('Frame3', thresholded[1])

    fgmask = fgbg.apply(avg)
    masks.add_frame(fgmask)
    fgmask = masks.get_average_frame()


    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (18, 18))
    fgmask = cv2.erode(fgmask, kernel, iterations=1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (18, 18))
    fgmask = cv2.dilate(fgmask, kernel, iterations=1)
    # kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (4, 4))
    # fgmask = cv2.morphologyEx(fgmask, cv2.MORPH_OPEN, kernel, iterations=2)



    # Нахождение контуров
    contours, _ = cv2.findContours(fgmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    max_contour = max(contours, key=lambda c: cv2.contourArea(c)) if contours else None
    if max_contour is not None:
        # Получаем координаты ограничивающего прямоугольника
        x, y, w, h = cv2.boundingRect(max_contour)
        cv2.rectangle(avg, (x, y), (x + w, y + h), (0, 255, 0), 2)

    avg = cv2.resize(avg, (640, 480))
    # Отображение результата
    cv2.imshow('Frame', avg)
    cv2.imshow('Foreground Mask', fgmask)
    cv2.imshow('Background', fgbg.getBackgroundImage())

    if cv2.waitKey(1) & 0xFF == 27:  # Нажмите Esc для выхода
        break

cap.release()
cv2.destroyAllWindows()


# import numpy as np
# import cv2
#
#
#
#
# # Пример использования
# if __name__ == "__main__":
#     cap = cv2.VideoCapture(0)  # Открываем веб-камеру
#
#     avg_buffer = AveragedFrameBuffer(frame_count=3)  # Создаем буфер для усреднения 30 кадров
#
#     while True:
#         ret, frame = cap.read()
#         if not ret:
#             break
#
#         avg_buffer.add_frame(frame)
#
#         average_frame = avg_buffer.get_average_frame()
#
#         cv2.imshow('Average Frame', average_frame)
#         cv2.imshow('Current Frame', frame)
#
#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             break
#
#     cap.release()
#     cv2.destroyAllWindows()

# import cv2
# import cv2 as cv
# import numpy as np
#
# # The video feed is read in as
# # a VideoCapture object
# cap = cv.VideoCapture(0)
#
# # ret = a boolean return value from
# # getting the frame, first_frame = the
# # first frame in the entire video sequence
# ret, first_frame = cap.read()
# first_frame = cv2.resize(first_frame, (160, 120))
#
# # Converts frame to grayscale because we
# # only need the luminance channel for
# # detecting edges - less computationally
# # expensive
# prev_gray = cv.cvtColor(first_frame, cv.COLOR_BGR2GRAY)
#
# # Creates an image filled with zero
# # intensities with the same dimensions
# # as the frame
# mask = np.zeros_like(first_frame)
#
# # Sets image saturation to maximum
# mask[..., 1] = 255
# prev_mask = mask
#
# while (cap.isOpened()):
#
#     # ret = a boolean return value from getting
#     # the frame, frame = the current frame being
#     # projected in the video
#     ret, frame = cap.read()
#
#     frame = cv2.resize(frame, (160, 120))
#
#     # Opens a new window and displays the input
#     # frame
#     cv.imshow("input", frame)
#
#     # Converts each frame to grayscale - we previously
#     # only converted the first frame to grayscale
#     gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
#
#     # Calculates dense optical flow by Farneback method
#     flow = cv.calcOpticalFlowFarneback(prev_gray, gray,
#                                        None,
#                                        0.1, 1, 1, 3, 1, 1.2, 0)
#
#     # Computes the magnitude and angle of the 2D vectors
#     magnitude, angle = cv.cartToPolar(flow[..., 0], flow[..., 1])
#
#     # Sets image hue according to the optical flow
#     # direction
#     mask[..., 0] = angle * 180 / np.pi / 2
#
#     # Sets image value according to the optical flow
#     # magnitude (normalized)
#     mask[..., 2] = cv.normalize(magnitude, None, 0, 255, cv.NORM_MINMAX)
#
#     cv.imshow("dense optical flow", rgb)
#
#     prev_mask = mask
#
#     # Converts HSV to RGB (BGR) color representation
#     rgb = cv.cvtColor(mask, cv.COLOR_HSV2BGR)
#
#     # Opens a new window and displays the output frame
#
#
#     # Updates previous frame
#     prev_gray = gray
#
#     # Frames are read by intervals of 1 millisecond. The
#     # programs breaks out of the while loop when the
#     # user presses the 'q' key
#     if cv.waitKey(1) & 0xFF == ord('q'):
#         break
#
# # The following frees up resources and
# # closes all windows
# cap.release()
# cv.destroyAllWindows()