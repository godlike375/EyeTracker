# -*- coding: utf-8 -*-
import os
import signal
import sys
import multiprocessing as mp
import time
import traceback
from dataclasses import dataclass
from multiprocessing.shared_memory import SharedMemory
from multiprocessing import Value
from threading import Thread
from datetime import datetime
from pathlib import Path
import copy
import ctypes
from typing import Any

import numpy as np
import cv2
from PySide6.QtWidgets import (QApplication, QMainWindow, QInputDialog)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QSurfaceFormat
from OpenGL.GL import *
from OpenGL.GL import shaders

from eye_tracker.common.native_rpc import RPCObjectServer

TARGET_RESOLUTION = (640, 480)
TARGET_FPS = 45
CAMERA_INDEX = 1
SHM_PREFIX = f"tracker_webcam_shm_"

DEGREE_TO_CV2_MAP = {
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
    0: None
}

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

def rotate_frame(frame: np.ndarray, degree: int):
    if degree and degree in DEGREE_TO_CV2_MAP:
        return cv2.rotate(frame, DEGREE_TO_CV2_MAP[degree])
    return frame

class VideoAdapter:
    def __init__(self, frame: np.ndarray, rotate_degree: Value, shm_name: str=None):
        self.height = frame.shape[0]
        self.width = frame.shape[1]
        self.shm_name = shm_name or f"{SHM_PREFIX}{os.getpid()}_{id(self)}"
        self.shared_memory = SharedMemory(name=self.shm_name, create=shm_name is None, size=frame.size * frame.itemsize)
        self.rotate_degree = rotate_degree
        self.video_frame = None

    def setup_video_frame(self):
        self.video_frame = np.ndarray((self.height, self.width, 3), dtype=np.uint8, buffer=self.shared_memory.buf)

    def get_ref_video_frame(self):
        if self.video_frame is None:
            raise RuntimeError("Video frame not initialized. Call setup_video_frame first.")
        return rotate_frame(self.video_frame, self.rotate_degree.value)

    def get_copy_video_frame(self):
        return np.copy(self.get_ref_video_frame())

    def get_transfer_data(self):
        return {
            'shm_name': self.shm_name,
            'height': self.height,
            'width': self.width,
            'rotate_degree': self.rotate_degree
        }

    @classmethod
    def from_transfer_data(cls, transfer_data):
        adapter = cls.__new__(cls)
        adapter.height = transfer_data['height']
        adapter.width = transfer_data['width']
        adapter.shm_name = transfer_data['shm_name']
        adapter.shared_memory = SharedMemory(name=adapter.shm_name)
        adapter.rotate_degree = transfer_data['rotate_degree']
        adapter.video_frame = None
        return adapter

    def close(self):
        if hasattr(self, 'shared_memory') and self.shared_memory:
            self.shared_memory.close()

def start_video_recording(filename, codec, fps, frame_size):
    fourcc = cv2.VideoWriter_fourcc(*codec)
    return cv2.VideoWriter(filename, fourcc, fps, frame_size)

def get_frame_props(cam_idx):
    cap = cv2.VideoCapture(cam_idx)
    if not cap.isOpened(): cap = cv2.VideoCapture(cam_idx + cv2.CAP_MSMF)
    if not cap.isOpened(): cap = cv2.VideoCapture(cam_idx + cv2.CAP_DSHOW)
    if not cap.isOpened():
        return None, None, None, None, None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, TARGET_RESOLUTION[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, TARGET_RESOLUTION[1])
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None, None, None, None, None
    h, w, _ = frame.shape
    dtype = np.uint8
    itemsize = np.dtype(dtype).itemsize
    size = h * w * 3 * itemsize
    return (h, w, 3), dtype, size, itemsize, frame

@dataclass
class ShareableEvent:
    _is_set: bool

    def is_set(self):
        return self._is_set

    def set(self):
        self._is_set = True

    def wait(self):
        while not self.is_set():
            time.sleep(0.05)

@dataclass
class ShareableValue:
    value: Any


class Model:
    def __init__(self, video_adapter_args, stop_event):
        self.video_adapter = VideoAdapter.from_transfer_data(video_adapter_args)
        self.points = []
        self.stop_event = stop_event
        self.run_thread = Thread(target=self.run, daemon=True)
        self.run_thread.start()

    def process_frame(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners = cv2.goodFeaturesToTrack(gray, maxCorners=100, qualityLevel=0.01, minDistance=10)
        if corners is not None:
            self.points = [(int(c[0][0]), int(c[0][1])) for c in corners]
        else:
            self.points = []

    def run(self):
        self.video_adapter.setup_video_frame()
        while not self.stop_event.is_set():
            frame_copy = self.video_adapter.get_copy_video_frame()
            self.process_frame(frame_copy)
            time.sleep(0.01)

class BaseVideoWidget:
    def __init__(self, video_adapter, stop_event):
        self.video_adapter = video_adapter
        self.frame_shape = (video_adapter.height, video_adapter.width, 3)
        self.frame_height, self.frame_width, self.frame_channels = self.frame_shape
        self.frame_dtype = np.uint8
        self.stop_event = stop_event
        self.frame_nbytes = self.frame_height * self.frame_width * self.frame_channels * np.dtype(self.frame_dtype).itemsize

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self._update)
        self.set_fps(int(TARGET_FPS))

    def set_fps(self, fps):
        interval = max(1, int(1000 / fps)) if fps > 0 else 1000
        self.timer.setInterval(interval)

    def _update(self):
        self.update()

    def showEvent(self, e):
        super().showEvent(e)
        self.timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()

class OpenGLVideoWidget(BaseVideoWidget, QOpenGLWidget):
    def __init__(self, video_adapter, stop_event, model, parent=None):
        QOpenGLWidget.__init__(self, parent)
        BaseVideoWidget.__init__(self, video_adapter, stop_event)
        self.model = model
        self.tex = None
        self.shader = None
        self.vao = None
        self.vbo = None
        self.ebo = None
        self.pbos = [None, None]
        self.pbo_index = 0

    def initializeGL(self):
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
        fmt.setSwapInterval(0)
        self.setFormat(fmt)
        glClearColor(0.0, 0.0, 0.0, 1.0)
        self.shader = shaders.compileProgram(
            shaders.compileShader(VERTEX_SHADER_SOURCE, GL_VERTEX_SHADER),
            shaders.compileShader(FRAGMENT_SHADER_SOURCE, GL_FRAGMENT_SHADER)
        )

        glUseProgram(self.shader)
        self.texture_loc = glGetUniformLocation(self.shader, "ourTexture")
        glDisable(GL_DEPTH_TEST)

        vertices = np.array([1.0, 1.0, 0.0, 1.0, 0.0,
                             1.0, -1.0, 0.0, 1.0, 1.0,
                             -1.0, -1.0, 0.0, 0.0, 1.0,
                             -1.0, 1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        indices = np.array([0, 1, 3, 1, 2, 3], dtype=np.uint32)

        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.ebo = glGenBuffers(1)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 5 * vertices.itemsize, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 5 * vertices.itemsize, ctypes.c_void_p(3 * vertices.itemsize))
        glEnableVertexAttribArray(1)
        glBindVertexArray(0)

        self.tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB8, self.frame_width, self.frame_height, 0, GL_BGR, GL_UNSIGNED_BYTE, None)

        self.pbos = glGenBuffers(2)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, self.pbos[0])
        glBufferData(GL_PIXEL_UNPACK_BUFFER, self.frame_nbytes, None, GL_STREAM_DRAW)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, self.pbos[1])
        glBufferData(GL_PIXEL_UNPACK_BUFFER, self.frame_nbytes, None, GL_STREAM_DRAW)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)

    def paint_objects(self):
        local_frame = self.video_adapter.get_copy_video_frame()
        points = self.model.points
        for point in points:
            cv2.circle(local_frame, point, 5, (0, 0, 255), -1)
        return local_frame

    def paintGL(self):
        local_frame = self.paint_objects()

        current_pbo = self.pbos[self.pbo_index]
        next_pbo = self.pbos[(self.pbo_index + 1) % 2]

        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, current_pbo)
        glBufferData(GL_PIXEL_UNPACK_BUFFER, self.frame_nbytes, None, GL_STREAM_DRAW)
        ptr = glMapBufferRange(GL_PIXEL_UNPACK_BUFFER, 0, self.frame_nbytes, GL_MAP_WRITE_BIT)
        if ptr is not None:
            ctypes.memmove(ptr, local_frame.ctypes.data, self.frame_nbytes)
            glUnmapBuffer(GL_PIXEL_UNPACK_BUFFER)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)

        glBindTexture(GL_TEXTURE_2D, self.tex)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, next_pbo)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.frame_width, self.frame_height, GL_BGR, GL_UNSIGNED_BYTE, None)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)

        glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(self.shader)
        glUniform1i(self.texture_loc, 0)
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)

        self.pbo_index = (self.pbo_index + 1) % 2

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)

class MainWindow(QMainWindow):
    def __init__(self, video_adapter: VideoAdapter, stop_event, model):
        super().__init__()
        self.stop_event = stop_event
        self.model = model
        self.video_adapter = video_adapter
        self.video_adapter.setup_video_frame()
        self.setWindowTitle("Webcam Viewer")
        self.resize(video_adapter.width, video_adapter.height)
        self.setMinimumSize(320, 240)

        self.opengl = OpenGLVideoWidget(video_adapter, stop_event, self.model, self)
        self.setCentralWidget(self.opengl)

        self.current_fps = int(TARGET_FPS)
        self._update_widget_fps(self.current_fps)
        self._create_menu()

    def _create_menu(self):
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
        exit_action = QAction("&Exit", self, triggered=self.close)
        file_menu.addAction(exit_action)

        view_menu = menu.addMenu("&View")
        set_fps_action = QAction("Set Render FPS", self, triggered=self.show_set_fps_dialog)
        rotate_action = QAction("Rotate Video", self, triggered=self.show_rotate_dialog)
        view_menu.addAction(set_fps_action)
        view_menu.addAction(rotate_action)

    def show_set_fps_dialog(self):
        fps, ok = QInputDialog.getInt(self, "Set Render FPS", "Enter target render FPS:", self.current_fps, 1, 10000, 1)
        if ok:
            self.current_fps = fps
            self._update_widget_fps(self.current_fps)

    def show_rotate_dialog(self):
        degrees = [0, 90, 180, 270]
        degree, ok = QInputDialog.getInt(self, "Rotate Video", "Enter rotation degree (0, 90, 180, 270):", self.video_adapter.rotate_degree.value, 0, 270, 90)
        if ok and degree in degrees:
            self.video_adapter.rotate_degree.value = degree

    def _update_widget_fps(self, fps):
        self.opengl.set_fps(fps)

    def closeEvent(self, e):
        self.stop_event.set()
        super().closeEvent(e)

def signal_handler(stop_event):
    if stop_event:
        stop_event.set()
    QTimer.singleShot(50, QApplication.quit)

def capture_process(video_adapter_data, stop_event):
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(stop_event))
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(stop_event))

    video_adapter = VideoAdapter.from_transfer_data(video_adapter_data)
    video_adapter.setup_video_frame()
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_ANY)
    if not cap.isOpened(): cap = cv2.VideoCapture(CAMERA_INDEX + cv2.CAP_MSMF)
    if not cap.isOpened(): cap = cv2.VideoCapture(CAMERA_INDEX + cv2.CAP_DSHOW)
    if not cap.isOpened():
        stop_event.set()
        video_adapter.close()
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, video_adapter.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, video_adapter.height)
    cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
    actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    needs_resize = not (int(actual_w) == video_adapter.width and int(actual_h) == video_adapter.height)

    while not stop_event.is_set():
        ret, current_frame = cap.read()
        if not ret:
            time.sleep(0.005)
            continue

        if needs_resize:
            current_frame = cv2.resize(current_frame, (video_adapter.width, video_adapter.height), interpolation=cv2.INTER_LINEAR)
        np.copyto(video_adapter.video_frame, current_frame)

    cap.release()
    video_adapter.close()

def run_model(video_adapter_data):
    server = RPCObjectServer(('localhost', 18812))
    server.stopped = ShareableEvent(False)
    server.instantiate_object_from_class('model', Model, video_adapter_data, server.stopped)
    return server, server.model, server.stopped

def display_process(video_adapter_data, model, stop_event):
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(stop_event))
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(stop_event))

    video_adapter = VideoAdapter.from_transfer_data(video_adapter_data)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    win = MainWindow(video_adapter, stop_event, model)
    win.show()
    exit_code = app.exec()
    stop_event.set()
    video_adapter.close()
    sys.exit(exit_code)

if __name__ == "__main__":
    mp.freeze_support()

    shape, dtype, size, itemsize, initial_frame = get_frame_props(CAMERA_INDEX)
    if shape is None:
        print(f"Failed to get frame properties from camera index {CAMERA_INDEX}")
        sys.exit(1)

    video_server = RPCObjectServer(('localhost', 18813), use_thread=True)
    video_server.rotate_degree = ShareableValue(0)
    video_adapter = VideoAdapter(initial_frame, video_server.rotate_degree)
    video_adapter_data = video_adapter.get_transfer_data()
    server, model, stop_event = run_model(video_adapter_data)
    capture_args = (video_adapter_data, stop_event)
    display_args = (video_adapter_data, model, stop_event)

    capture_proc = mp.Process(target=capture_process, args=capture_args, name="CaptureProcess")
    display_proc = mp.Process(target=display_process, args=display_args, name="DisplayProcess")

    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(stop_event))
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(stop_event))

    try:
        capture_proc.start()
        display_proc.start()
        display_proc.join()
    except Exception as e:
        print(f"Unhandled exception: {traceback.format_exc()}")
    finally:
        stop_event.set()
        if display_proc.is_alive(): display_proc.terminate()
        if capture_proc.is_alive(): capture_proc.join(timeout=1), capture_proc.terminate()
        server.terminate_and_join()
        video_adapter.shared_memory.unlink()
        video_adapter.close()
        sys.exit(0)