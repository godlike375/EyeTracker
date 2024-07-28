import argparse
import multiprocessing
import sys
from multiprocessing import Process

import cv2
from PyQt6.QtWidgets import QApplication

from tracker.camera import VideoAdapter, stream_video
from tracker.ui.main_controller import MainController
from tracker.ui.main_window import MainWindow
from tracker.utils.shared_objects import SharedFlag

sys.path.append('..')


def main(video_adapter: VideoAdapter, args, recording: SharedFlag):
    app = QApplication(sys.argv)
    window = MainWindow()
    frontend = MainController(window, video_adapter, recording, args.fps, args.ui_fps)
    window.new_tracker.connect(frontend.on_new_tracker_requested)
    window.rotate.connect(frontend.on_rotate)
    window.rotate.connect(window.video_label.on_rotate)
    window.start_calibration.connect(frontend.on_calibration_started)
    window.stop_calibration.connect(frontend.on_calibration_stopped)
    window.start_recording.connect(frontend.on_recording_started)
    window.stop_recording.connect(frontend.on_recording_stopped)
    window.show()
    code = app.exec()
    for p in frontend.processes:
        p.kill()
    sys.exit(code)


if __name__ == '__main__':
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--id_camera',
                        type=str, default='0')
    parser.add_argument('-f', '--fps',
                        type=int, default=120)
    parser.add_argument('-r', '--resolution',
                        type=int, default=640)
    parser.add_argument('-uf', '--ui_fps',
                        type=int, default=25)
    args = parser.parse_args(sys.argv[1:])
    try:
        args.id_camera = int(args.id_camera)
    except:
        ...
    camera = cv2.VideoCapture(args.id_camera)
    camera.set(cv2.CAP_PROP_FPS, args.fps)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, args.resolution)
    captured, frame = camera.read()
    if not captured:
        raise IOError("can't access camera")
    video_adapter = VideoAdapter(frame)
    recording = SharedFlag(False)

    main_process = Process(target=main, args=(video_adapter, args, recording))
    main_process.start()

    stream_video(camera, video_adapter, recording, args.id_camera, args.fps, args.resolution)