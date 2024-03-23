from threading import Thread
from time import time, sleep
import sys

import cv2
import dlib

from eye_tracker.common.coordinates import Point
from eye_tracker.view.drawing import Processor
from frame_processing import Tracker

sys.setswitchinterval(1)

# define a video capture object
vid = cv2.VideoCapture(0)
tracker = Tracker()

#tracker = dlib.correlation_tracker()
tracker_in_progress = False

class FrameStorage:
    def __init__(self):
        ret, self.frame = vid.read()

fs = FrameStorage()

SHOW_FRAME_EVERY_N_FRAMES = 30
n_frames = 0

def capture_frames():
    global fs
    while True:
        if n_frames % SHOW_FRAME_EVERY_N_FRAMES == 0:
            ret, fs.frame = vid.read()
        else:
            sleep(0.1)

fs_thread = Thread(target=capture_frames, daemon=True)
fs_thread.start()


frame_time = time()

#frame = Processor.resize_frame_relative(frame, 0.1)
while (True):

    # Capture the video frame
    # by frame
    frame = fs.frame

    if not tracker.in_progress:
        #rect = dlib.rectangle(280, 420, 320, 480)
        #rect = dlib.rectangle(10, 10, 20, 20)
        #tracker.start_track(frame, rect)
        #tracker_in_progress = True
        tracker.start_tracking(frame, Point(280, 420),  Point(320, 480), frame.shape[1], frame.shape[0])


    else:
        position = tracker.get_tracked_position(frame)
        # tracker.update(frame)
        # pos = tracker.get_position()
        # # unpack the position object
        # startX = int(pos.left())
        # startY = int(pos.top())
        # endX = int(pos.right())
        # endY = int(pos.bottom())
        if n_frames % SHOW_FRAME_EVERY_N_FRAMES == 0:
            frame = Processor.draw_rectangle(frame, Point(position.x - 50, position.y - 50),
                                            Point(position.x + 50, position.y + 50))


    # Display the resulting frame
    if n_frames % SHOW_FRAME_EVERY_N_FRAMES == 0:
        cv2.imshow('frame', frame)

    n_frames += 1

    if n_frames % SHOW_FRAME_EVERY_N_FRAMES == 0:
        cur_time = time()
        print(1 / ((cur_time - frame_time) / SHOW_FRAME_EVERY_N_FRAMES))
        frame_time = cur_time
    # the 'q' button is set as the
    # quitting button you may use any
    # desired button of your choice
    #if cv2.waitKey(1) & 0xFF == ord('q'):
    #    break

# After the loop release the cap object
vid.release()
# Destroy all the windows
cv2.destroyAllWindows()