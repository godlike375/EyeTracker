from threading import Thread

import cv2
from pupil_detectors import Detector2D

from tracker.utils.fps import FPSCounter

detector = Detector2D()

video_capture = cv2.VideoCapture(1)
fps = FPSCounter()

ret, image = video_capture.read()

def camera_get():
    global image
    while True:
        ret, image = video_capture.read()

cam_thread = Thread(target=camera_get, daemon=True)
cam_thread.start()

while True:
    fps.count_frame()
    if fps.able_to_calculate():
        print(fps.calculate())
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    result = detector.detect(gray)
    ellipse = result["ellipse"]

    # draw the ellipse outline onto the input image
    # note that cv2.ellipse() cannot deal with float values
    # also it expects the axes to be semi-axes (half the size)
    cv2.ellipse(
       image,
       tuple(int(v) for v in ellipse["center"]),
       tuple(int(v / 2) for v in ellipse["axes"]),
       ellipse["angle"],
       0, 360, # start/end angle for drawing
       (0, 0, 255) # color (BGR): red
    )
    cv2.imshow("Image", image)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# When everything is done, release the capture
video_capture.release()
cv2.destroyAllWindows()