# -*- coding: utf-8 -*-
import argparse
import sys
import multiprocessing as mp
import time
import numpy as np
import cv2

from PySide6.QtWidgets import QApplication

sys.path.insert(0, '.')
from tracker.camera import VideoAdapter
from view.main_window import MainWindow

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--id_camera', type=str, default='0')
parser.add_argument('-f', '--fps', type=int, default=15)
parser.add_argument('-r', '--resolution', type=int, default=1280)
args = parser.parse_args(sys.argv[1:])

try:
    CAMERA_INDEX = int(args.id_camera)
except (ValueError, TypeError):
    CAMERA_INDEX = args.id_camera

TARGET_RESOLUTION = (args.resolution, int(args.resolution * 720 / 1280))
TARGET_FPS = args.fps


def get_initial_frame_props(video_source=None):
    if video_source is None or isinstance(video_source, int):
        idx = video_source if isinstance(video_source, int) else CAMERA_INDEX
        cap = cv2.VideoCapture(idx)
    else:
        cap = cv2.VideoCapture(str(video_source))

    if not cap or not cap.isOpened():
        shape = (TARGET_RESOLUTION[1], TARGET_RESOLUTION[0], 3)
        return shape, np.uint8, np.zeros(shape, dtype=np.uint8)

    ret, frame = cap.read()
    cap.release()
    if not ret:
        shape = (TARGET_RESOLUTION[1], TARGET_RESOLUTION[0], 3)
        return shape, np.uint8, np.zeros(shape, dtype=np.uint8)

    frame = cv2.resize(frame, TARGET_RESOLUTION)
    return frame.shape, frame.dtype, frame


def capture_worker(adapter: VideoAdapter, stop_event, source_queue, initial_source):
    adapter.setup_video_frame()
    current_source = initial_source
    cap = None

    def open_cap(src):
        nonlocal cap
        if cap:
            cap.release()
        return cv2.VideoCapture(CAMERA_INDEX if src is None else str(src))

    cap = open_cap(current_source)

    while not stop_event.is_set():
        if not source_queue.empty():
            current_source = source_queue.get()
            cap = open_cap(current_source)

        ret, frame = cap.read()
        if not ret:
            if current_source is not None:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        if (frame.shape[1], frame.shape[0]) != TARGET_RESOLUTION:
            frame = cv2.resize(frame, TARGET_RESOLUTION)

        np.copyto(adapter.video_frame, frame)
        time.sleep(1 / TARGET_FPS)

    if cap:
        cap.release()
    adapter.close()


if __name__ == "__main__":
    mp.freeze_support()

    _, _, init_frame = get_initial_frame_props()
    rotate_val = mp.Value('i', 0)
    adapter = VideoAdapter(init_frame, rotate_val)

    stop_event = mp.Event()
    source_queue = mp.Queue()
    roi_array = mp.Array('i', [0, 0, 0, 0])

    capture_proc = mp.Process(
        target=capture_worker,
        args=(adapter.send_to_process(), stop_event, source_queue, None),
        name="Capture"
    )
    capture_proc.start()

    app = QApplication(sys.argv)
    adapter.setup_video_frame()

    win = MainWindow(adapter, stop_event, source_queue, roi_array)
    win.show()

    app.exec()

    stop_event.set()
    capture_proc.join(timeout=2)
    if capture_proc.is_alive():
        capture_proc.terminate()

    adapter.shared_memory.unlink()
    adapter.close()
