import argparse
import multiprocessing
import sys

from PyQt6.QtWidgets import QApplication

from tracker.ui.frontend import Frontend
from tracker.ui.main_window import MainWindow

sys.path.append('..')

if __name__ == '__main__':
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--id_camera',
                        type=str, default='0')
    parser.add_argument('-f', '--fps',
                        type=int, default=120)
    parser.add_argument('-r', '--resolution',
                        type=int, default=640)
    args = parser.parse_args(sys.argv[1:])
    app = QApplication(sys.argv)
    window = MainWindow()
    try:
        args.id_camera = int(args.id_camera)
    except:
        ...
    frontend = Frontend(window, args.id_camera, args.fps, args.resolution)
    window.new_tracker.connect(frontend.on_new_tracker_requested)
    window.select_eye.connect(frontend.on_eye_select_requested)
    window.show()
    sys.exit(app.exec())