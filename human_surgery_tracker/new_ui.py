# -*- coding: utf-8 -*-
import os
import signal
import sys
import multiprocessing as mp
import time
import traceback
from multiprocessing.shared_memory import SharedMemory

import numpy as np
import cv2
from PySide6.QtWidgets import (QApplication, QMainWindow, QStackedWidget, QLabel,
                               QVBoxLayout, QInputDialog, QWidget)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage, QPixmap, QAction, QSurfaceFormat, QActionGroup
from OpenGL.GL import *
from OpenGL.GL import shaders
from tracker.utils.fps import FPSCounter

TARGET_RESOLUTION = (640, 480)
TARGET_FPS = 45
CAMERA_INDEX = 0
SHM_PREFIX = f"tracker_webcam_shm_"

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

def get_frame_props(cam_idx):
    cap = cv2.VideoCapture(cam_idx)
    ret, frame = cap.read()
    cap.release()
    h, w, _ = frame.shape
    dtype = np.uint8
    itemsize = np.dtype(dtype).itemsize
    size = h * w * 3 * itemsize
    return (h, w, 3), dtype, size, itemsize

class BaseVideoWidget:
    def __init__(self, shm_name_data, frame_shape, frame_dtype, stop_event):
        self.shm_name = shm_name_data
        self.frame_shape = frame_shape
        self.frame_height, self.frame_width, self.frame_channels = frame_shape
        self.frame_dtype = frame_dtype
        self.stop_event = stop_event
        self.fps = FPSCounter()
        self.frame_nbytes = self.frame_height * self.frame_width * self.frame_channels * np.dtype(self.frame_dtype).itemsize

        self.shm = mp.shared_memory.SharedMemory(name=self.shm_name)
        self.frame = np.ndarray(self.frame_shape, dtype=self.frame_dtype, buffer=self.shm.buf)

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self._update)
        self.set_fps(int(TARGET_FPS))

    def set_fps(self, fps):
        interval = max(1, int(1000 / fps)) if fps > 0 else 1000
        self.timer.setInterval(interval)

    def _update(self):
        self.fps.count_frame()
        if self.fps.able_to_calculate():
            print(f"{self.__class__.__name__} Render FPS: {self.fps.calculate():.2f}")
        self.render()

    def render(self):
        raise NotImplementedError

    def showEvent(self, e):
        super().showEvent(e)
        self.timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()

    # TODO: remove if unused
    # def closeEvent(self, e):
    #     self._cleanup()
    #     super().closeEvent(e)
    #
    # def _cleanup(self):
    #     if self.timer.isActive():
    #         self.timer.stop()
    #     if hasattr(self, 'shm') and self.shm:
    #         self.shm.close()
    #     self.frame = None


class OpenGLVideoWidget(BaseVideoWidget, QOpenGLWidget):
    def __init__(self, shm_name, shape, dtype, stop_event, parent=None):
        QOpenGLWidget.__init__(self, parent)
        BaseVideoWidget.__init__(self, shm_name, shape, dtype, stop_event)

        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
        fmt.setSwapInterval(0)
        self.setFormat(fmt)

        self.tex = None
        self.shader = None
        self.vao = None
        self.vbo = None
        self.ebo = None
        self.pbos = [None, None]
        self.pbo_index = 0

    def initializeGL(self):
        glClearColor(0.0, 0.0, 0.0, 1.0)
        self.shader = shaders.compileProgram(
            shaders.compileShader(VERTEX_SHADER_SOURCE, GL_VERTEX_SHADER),
            shaders.compileShader(FRAGMENT_SHADER_SOURCE, GL_FRAGMENT_SHADER)
        )

        vertices = np.array([ 1.0,  1.0, 0.0,  1.0, 0.0,
                              1.0, -1.0, 0.0,  1.0, 1.0,
                             -1.0, -1.0, 0.0,  0.0, 1.0,
                             -1.0,  1.0, 0.0,  0.0, 0.0 ], dtype=np.float32)
        indices = np.array([ 0, 1, 3, 1, 2, 3 ], dtype=np.uint32)

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
        glBindVertexArray(0) # Unbind VAO first
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)


        self.tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self.frame_width, self.frame_height, 0, GL_BGR, GL_UNSIGNED_BYTE, None)
        glBindTexture(GL_TEXTURE_2D, 0)

        self.pbos = glGenBuffers(2)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, self.pbos[0])
        glBufferData(GL_PIXEL_UNPACK_BUFFER, self.frame_nbytes, None, GL_STREAM_DRAW)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, self.pbos[1])
        glBufferData(GL_PIXEL_UNPACK_BUFFER, self.frame_nbytes, None, GL_STREAM_DRAW)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)

    def paintGL(self):
        current_pbo = self.pbos[self.pbo_index]
        next_pbo = self.pbos[(self.pbo_index + 1) % 2]

        glBindTexture(GL_TEXTURE_2D, self.tex)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, current_pbo)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.frame_width, self.frame_height, GL_BGR, GL_UNSIGNED_BYTE, ctypes.c_void_p(0))

        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, next_pbo)
        ptr = glMapBufferRange(GL_PIXEL_UNPACK_BUFFER, 0, self.frame_nbytes, GL_MAP_WRITE_BIT | GL_MAP_INVALIDATE_BUFFER_BIT)
        ctypes.memmove(ptr, self.frame.ctypes.data, self.frame.nbytes)
        glUnmapBuffer(GL_PIXEL_UNPACK_BUFFER)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)

        glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(self.shader)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.tex)
        glUniform1i(glGetUniformLocation(self.shader, "ourTexture"), 0)

        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)

        glBindVertexArray(0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glUseProgram(0)

        self.pbo_index = (self.pbo_index + 1) % 2

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)

    def render(self):
        self.update()

    # TODO: remove if unused
    # def _cleanup(self):
    #     print("OpenGLVideoWidget.closeEvent called")
    #     self.makeCurrent()
    #     if self.tex is not None: glDeleteTextures([self.tex])
    #     if self.vbo is not None: glDeleteBuffers(1, [self.vbo])
    #     if self.ebo is not None: glDeleteBuffers(1, [self.ebo])
    #     if self.vao is not None: glDeleteVertexArrays(1, [self.vao])
    #     if self.pbos[0] is not None: glDeleteBuffers(2, self.pbos)
    #     if self.shader is not None: glDeleteProgram(self.shader)
    #     self.doneCurrent()
    #     BaseVideoWidget._cleanup(self)
    #     self.tex = self.vbo = self.ebo = self.vao = self.shader = None
    #     self.pbos = [None, None]


class QLabelVideoWidget(BaseVideoWidget, QWidget):
    def __init__(self, shm_name, shape, dtype, stop_event, parent=None):
        QWidget.__init__(self, parent)
        BaseVideoWidget.__init__(self, shm_name, shape, dtype, stop_event)
        self.label = QLabel(self)
        self.label.setScaledContents(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

    def render(self):
        h, w, _ = self.frame.shape
        img = QImage(self.frame.data, w, h, w * 3, QImage.Format.Format_BGR888)
        self.label.setPixmap(QPixmap.fromImage(img))


class MainWindow(QMainWindow):
    def __init__(self, shm_name, shape, dtype, stop_event):
        super().__init__()
        self.stop_event = stop_event
        self.setWindowTitle("Webcam Viewer")
        self.resize(shape[1], shape[0])
        self.setMinimumSize(320, 240)

        self.stack = QStackedWidget(self)
        self.opengl = OpenGLVideoWidget(shm_name, shape, dtype, stop_event, self)
        self.label = QLabelVideoWidget(shm_name, shape, dtype, stop_event, self)
        self.stack.addWidget(self.opengl)
        self.stack.addWidget(self.label)
        self.setCentralWidget(self.stack)

        self.current_fps = int(TARGET_FPS)
        self._update_widget_fps(self.current_fps)
        self._create_menu()
        self.stack.setCurrentIndex(0)

    def _create_menu(self):
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
        exit_action = QAction("&Exit", self, triggered=self.close)
        file_menu.addAction(exit_action)

        view_menu = menu.addMenu("&View")
        render_group = QActionGroup(self)
        render_group.setExclusive(True)
        self.opengl_act = QAction("OpenGL", self, checkable=True, checked=True, triggered=lambda: self.stack.setCurrentIndex(0))
        self.label_act = QAction("QLabel", self, checkable=True, triggered=lambda: self.stack.setCurrentIndex(1))
        render_group.addAction(self.opengl_act)
        render_group.addAction(self.label_act)
        view_menu.addAction(self.opengl_act)
        view_menu.addAction(self.label_act)

        set_fps_action = QAction("Set Render FPS", self, triggered=self.show_set_fps_dialog)
        view_menu.addAction(set_fps_action)

    def show_set_fps_dialog(self):
        fps, ok = QInputDialog.getInt(self, "Set Render FPS", "Enter target render FPS:", self.current_fps, 1, 10000, 1)
        if ok:
            self.current_fps = fps
            self._update_widget_fps(self.current_fps)

    def _update_widget_fps(self, fps):
        self.opengl.set_fps(fps)
        self.label.set_fps(fps)

    def closeEvent(self, e):
        self.stop_event.set()
        super().closeEvent(e)


def signal_handler(stop_event):
    if stop_event:
        stop_event.set()
    QTimer.singleShot(50, QApplication.quit)


def capture_process(shm_name, shape, dtype, stop_event):
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(stop_event))
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(stop_event))

    shm = mp.shared_memory.SharedMemory(name=shm_name)
    frame_buffer = np.ndarray(shape, dtype=dtype, buffer=shm.buf)
    fps_counter = FPSCounter()

    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_ANY)
    if not cap.isOpened(): cap = cv2.VideoCapture(CAMERA_INDEX + cv2.CAP_MSMF)
    if not cap.isOpened(): cap = cv2.VideoCapture(CAMERA_INDEX + cv2.CAP_DSHOW)
    if not cap.isOpened():
        stop_event.set()
        shm.close()
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, shape[1])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, shape[0])
    cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
    actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    needs_resize = not (int(actual_w) == shape[1] and int(actual_h) == shape[0])

    while not stop_event.is_set():
        ret, current_frame = cap.read()
        if not ret:
            time.sleep(0.005)
            continue

        fps_counter.count_frame()
        if fps_counter.able_to_calculate():
             print(f"Capture FPS: {fps_counter.calculate():.2f}")

        if needs_resize:
            current_frame = cv2.resize(current_frame, (shape[1], shape[0]), interpolation=cv2.INTER_LINEAR)
        np.copyto(frame_buffer, current_frame)

    cap.release()
    shm.close()


def display_process(shm_name, shape, dtype, stop_event):
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(stop_event))
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(stop_event))

    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    win = MainWindow(shm_name, shape, dtype, stop_event)
    win.show()
    exit_code = app.exec()
    stop_event.set()
    sys.exit(exit_code)

if __name__ == "__main__":
    mp.freeze_support()

    shape, dtype, size, itemsize = get_frame_props(CAMERA_INDEX)
    stop_event = mp.Event()
    shm_name = f"{SHM_PREFIX}{os.getpid()}"
    shm = None

    try:
        shm = SharedMemory(name=shm_name, create=True, size=int(size))
    except Exception as e:
        print(f"Couldn't create shared memory segment with name={shm_name}")
        sys.exit(1)

    capture_args = (shm_name, shape, dtype, stop_event)
    display_args = (shm_name, shape, dtype, stop_event)

    capture_proc = mp.Process(target=capture_process, args=capture_args, name="CaptureProcess")
    display_proc = mp.Process(target=display_process, args=display_args, name="DisplayProcess")

    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(stop_event))
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(stop_event))

    try:
        capture_proc.start()
        display_proc.start()
        display_proc.join()
    except Exception as e: print(f"Unhandled expection: {traceback.format_exc()}")
    finally:
        stop_event.set()
        capture_proc.join(timeout=2)
        if display_proc.is_alive(): display_proc.join(timeout=1) # Should be joined already

        if capture_proc.is_alive(): capture_proc.terminate()
        if display_proc.is_alive(): display_proc.terminate()

        if shm is not None:
            try:
                shm.unlink()
            except: ...
            finally:
                 shm.close()

        sys.exit(0)