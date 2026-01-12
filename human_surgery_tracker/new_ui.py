# -*- coding: utf-8 -*-
import argparse
import sys
import multiprocessing as mp
import time
import numpy as np
import cv2

from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import QTimer, Qt, QPoint
from OpenGL.GL import *
from OpenGL.GL import shaders

# Импорты проекта
sys.path.insert(0, '.')
from new_settings import AppSettings, SettingsWindow
from tracker.camera import VideoAdapter
from tracker.detectors.eye_pupil_detector import EyePupilDetector
from tracker.utils.shared_objects import SharedBox, INITIAL_VALUE

# --- Парсинг аргументов командной строки ---
parser = argparse.ArgumentParser()
parser.add_argument('-i', '--id_camera',
                    type=str, default='0')
parser.add_argument('-f', '--fps',
                    type=int, default=15)
parser.add_argument('-r', '--resolution',
                    type=int, default=1280)
args = parser.parse_args(sys.argv[1:])

# Преобразование id_camera в int, если возможно
try:
    CAMERA_INDEX = int(args.id_camera)
except:
    CAMERA_INDEX = args.id_camera

# --- Константы ---
# Вычисляем высоту на основе ширины, сохраняя соотношение сторон 16:9 (1280x720)
TARGET_RESOLUTION = (args.resolution, int(args.resolution * 720 / 1280))
TARGET_FPS = args.fps

VERTEX_SHADER_SOURCE = """
#version 330 core
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec2 aTexCoord;
out vec2 TexCoord;
void main() {
    gl_Position = vec4(aPos, 1.0);
    TexCoord = aTexCoord;
}
"""

FRAGMENT_SHADER_SOURCE = """
#version 330 core
out vec4 FragColor;
in vec2 TexCoord;
uniform sampler2D ourTexture;
void main() {
    FragColor = texture(ourTexture, TexCoord);
}
"""

def get_initial_frame_props(video_source=None):
    if video_source is None or isinstance(video_source, int):
        idx = video_source if isinstance(video_source, int) else CAMERA_INDEX
        cap = cv2.VideoCapture(idx)
    else:
        cap = cv2.VideoCapture(str(video_source))

    if not cap or not cap.isOpened():
        return (TARGET_RESOLUTION[1], TARGET_RESOLUTION[0], 3), np.uint8, np.zeros((TARGET_RESOLUTION[1], TARGET_RESOLUTION[0], 3), dtype=np.uint8)

    ret, frame = cap.read()
    cap.release()
    if not ret:
        frame = np.zeros((TARGET_RESOLUTION[1], TARGET_RESOLUTION[0], 3), dtype=np.uint8)

    frame = cv2.resize(frame, TARGET_RESOLUTION)
    return frame.shape, frame.dtype, frame


def capture_worker(adapter: VideoAdapter, stop_event, source_queue, initial_source):
    adapter.setup_video_frame()
    current_source = initial_source
    cap = None

    def open_cap(src):
        nonlocal cap
        if cap: cap.release()
        return cv2.VideoCapture(CAMERA_INDEX if src is None else str(src))

    cap = open_cap(current_source)

    while not stop_event.is_set():
        if not source_queue.empty():
            current_source = source_queue.get()
            cap = open_cap(current_source)

        ret, frame = cap.read()
        if not ret:
            if current_source is not None: cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        if (frame.shape[1], frame.shape[0]) != TARGET_RESOLUTION:
            frame = cv2.resize(frame, TARGET_RESOLUTION)

        np.copyto(adapter.video_frame, frame)
        time.sleep(1/TARGET_FPS)

    if cap: cap.release()
    adapter.close()

# --- ИЗМЕНЕННЫЙ КЛАСС ВИДЖЕТА ---

class OpenGLVideoWidget(QOpenGLWidget):
    def __init__(self, adapter, main_window: 'MainWindow', roi_array, parent=None):
        super().__init__(parent)
        self.adapter = adapter
        self.main_window = main_window
        self.roi_array = roi_array
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.selection_start = None
        self.selection_end = None
        self.is_selecting = False
        self.tex = None
        self.shader = None
        self.vao = None
        self.pbos = [None, None]
        self.pbo_idx = 0

    def initializeGL(self):
        self.shader = shaders.compileProgram(
            shaders.compileShader(VERTEX_SHADER_SOURCE, GL_VERTEX_SHADER),
            shaders.compileShader(FRAGMENT_SHADER_SOURCE, GL_FRAGMENT_SHADER)
        )
        vertices = np.array([
            1.0,  1.0, 0.0, 1.0, 0.0,
            1.0, -1.0, 0.0, 1.0, 1.0,
            -1.0, -1.0, 0.0, 0.0, 1.0,
            -1.0,  1.0, 0.0, 0.0, 0.0
        ], dtype=np.float32)
        indices = np.array([0, 1, 3, 1, 2, 3], dtype=np.uint32)
        self.vao = glGenVertexArrays(1)
        vbo, ebo = glGenBuffers(2)
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 20, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 20, ctypes.c_void_p(12))
        glEnableVertexAttribArray(1)
        self.tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB8, TARGET_RESOLUTION[0], TARGET_RESOLUTION[1], 0, GL_BGR, GL_UNSIGNED_BYTE, None)
        self.pbos = glGenBuffers(2)
        for pbo in self.pbos:
            glBindBuffer(GL_PIXEL_UNPACK_BUFFER, pbo)
            glBufferData(GL_PIXEL_UNPACK_BUFFER, TARGET_RESOLUTION[0]*TARGET_RESOLUTION[1]*3, None, GL_STREAM_DRAW)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)

    def paintGL(self):
        frame = self.adapter.get_copy_video_frame()

        if self.main_window.detector and self.main_window.detector.pupil_detector.pupil:
            pupil = self.main_window.detector.pupil_detector.pupil
            if pupil.x != -1:
                px, py = int(pupil.x), int(pupil.y)
                cv2.circle(frame, (px, py), 6, (0, 255, 0), -1)
                cv2.circle(frame, (px, py), 7, (255, 255, 255), 1)

        if self.is_selecting and self.selection_start and self.selection_end:
            cv2.rectangle(frame, self._to_frame_coords(self.selection_start),
                          self._to_frame_coords(self.selection_end), (255, 0, 255), 2)

        h, w = frame.shape[:2]
        self.pbo_idx = (self.pbo_idx + 1) % 2
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, self.pbos[self.pbo_idx])
        ptr = glMapBufferRange(GL_PIXEL_UNPACK_BUFFER, 0, frame.nbytes, GL_MAP_WRITE_BIT)
        if ptr:
            ctypes.memmove(ptr, frame.ctypes.data, frame.nbytes)
            glUnmapBuffer(GL_PIXEL_UNPACK_BUFFER)

        glBindTexture(GL_TEXTURE_2D, self.tex)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_BGR, GL_UNSIGNED_BYTE, None)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)

        glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(self.shader)
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)

    def _to_frame_coords(self, pt: QPoint):
        scale_x = TARGET_RESOLUTION[0] / self.width()
        scale_y = TARGET_RESOLUTION[1] / self.height()
        return (int(pt.x() * scale_x), int(pt.y() * scale_y))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.selection_start = e.position().toPoint()
            self.selection_end = e.position().toPoint()
            self.is_selecting = True

    def mouseMoveEvent(self, e):
        if self.is_selecting:
            self.selection_end = e.position().toPoint()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.is_selecting = False
            p1 = self._to_frame_coords(self.selection_start)
            p2 = self._to_frame_coords(self.selection_end)
            self.roi_array[:] = [min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1])]

class MainWindow(QMainWindow):
    def __init__(self, adapter, stop_event, source_queue, roi_array):
        super().__init__()
        self.adapter = adapter
        self.stop_event = stop_event
        self.source_queue = source_queue
        self.roi_array = roi_array
        self.detector = None
        self.last_roi = None

        self.setWindowTitle("Multi-Process Eye Tracker")
        self.gl_widget = OpenGLVideoWidget(adapter, self, roi_array, self)
        self.setCentralWidget(self.gl_widget)
        self.resize(TARGET_RESOLUTION[0], TARGET_RESOLUTION[1])

        self.settings = AppSettings({
            "render_fps": {"value": TARGET_FPS, "min": 1, "max": 144},
            "rotate_degree": {"value": 0, "min": 0, "max": 270},
        })

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_detector)
        self.update_timer.start(16)

        self._create_menu()
        self.gl_widget.timer.start(1000 // TARGET_FPS)

    def _update_detector(self):
        current_roi = list(self.roi_array)
        if current_roi != self.last_roi and current_roi[2] > 0:
            if self.detector:
                self.detector.stop_process()
            eye_area = SharedBox('i', INITIAL_VALUE)
            eye_area.left_top.x, eye_area.left_top.y = current_roi[0], current_roi[1]
            eye_area.right_bottom.x, eye_area.right_bottom.y = current_roi[2], current_roi[3]
            self.detector = EyePupilDetector(
                eyes_count=1,
                averaging_frames_count=2,
                eye_detect_area=eye_area,
                video_adapter=self.adapter,
                target_fps=60
            )
            self.detector.start_process()
            self.last_roi = current_roi

    def _create_menu(self):
        bar = self.menuBar()
        file_menu = bar.addMenu("File")

        file_menu.addAction("Open Video", self._open_file)
        file_menu.addAction("Use Camera", self._open_camera)
        file_menu.addSeparator()
        file_menu.addAction("Settings", self._show_settings)
        file_menu.addAction("Exit", self.close)

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Video")
        if path: self.source_queue.put(path)

    def _open_camera(self):
        self.source_queue.put(None)

    def _show_settings(self):
        fields = [("render_fps", "FPS:"), ("rotate_degree", "Rotation:")]
        if SettingsWindow(self.settings, fields, self).exec():
            self.gl_widget.timer.setInterval(1000 // self.settings.render_fps)
            self.adapter.rotate_degree.value = self.settings.rotate_degree

    def closeEvent(self, e):
        if self.detector:
            self.detector.stop_process()
        self.stop_event.set()
        super().closeEvent(e)

# --- Main ---

if __name__ == "__main__":
    mp.freeze_support()

    # 1. Инициализация общих данных
    _, _, init_frame = get_initial_frame_props()
    rotate_val = mp.Value('i', 0)
    adapter = VideoAdapter(init_frame, rotate_val)
    adapter_data = adapter.get_transfer_data()

    stop_event = mp.Event()
    source_queue = mp.Queue()
    roi_array = mp.Array('i', [0, 0, 0, 0])

    capture_proc = mp.Process(target=capture_worker, args=(adapter.send_to_process(), stop_event, source_queue, None), name="Capture")
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