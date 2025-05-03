# -*- coding: utf-8 -*-
import signal
import sys
import multiprocessing as mp
import time
import uuid
from multiprocessing.shared_memory import SharedMemory

import numpy as np
import cv2
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QLabel, QVBoxLayout, QInputDialog, QWidget
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage, QPixmap, QAction, QSurfaceFormat, QActionGroup
from OpenGL.GL import *
from OpenGL.GL import shaders
from tracker.utils.fps import FPSCounter

TARGET_RESOLUTION = (640, 480)
TARGET_FPS = 45 * 1.05
CAMERA_INDEX = 0
SHM_PREFIX = f"webcam_shm_gl_{uuid.uuid4()}"
QT_TIMER_INTERVAL = round(1000 / TARGET_FPS)

VERTEX_SHADER_SOURCE = """
#version 330 core
layout (location = 0) in vec3 aPos; layout (location = 1) in vec2 aTexCoord;
out vec2 TexCoord; void main() { gl_Position = vec4(aPos, 1.0); TexCoord = aTexCoord; }
"""

FRAGMENT_SHADER_SOURCE = """
#version 330 core
out vec4 FragColor; in vec2 TexCoord; uniform sampler2D ourTexture;
void main() { FragColor = texture(ourTexture, TexCoord); }
"""


def get_frame_props(cam_idx):
    cap = cv2.VideoCapture(cam_idx)
    if not cap.isOpened(): return None, None, None
    frame = None
    for _ in range(5):
        ret, frame = cap.read()
        if ret and frame is not None: break
        time.sleep(0.1)
    if frame is None: return None, None, None
    h, w, c = frame.shape
    dtype = frame.dtype.name
    size = np.prod((h, w, c)) * np.dtype(dtype).itemsize
    cap.release()
    return (h, w, c), dtype, size


class BaseVideoWidget:
    def __init__(self, shm_name_data, frame_shape, frame_dtype_name, stop_event):
        self.shm_name_data = shm_name_data
        self.frame_shape = frame_shape
        self.frame_height, self.frame_width, self.frame_channels = frame_shape
        self.frame_dtype = np.dtype(frame_dtype_name)
        self.stop_event = stop_event
        self.shared_frame_bgr = None
        self.existing_shm_data = None
        self.fps = FPSCounter()

        self._init_shm()
        self._init_timer()

    def _init_shm(self):
        try:
            self.shm = mp.shared_memory.SharedMemory(name=self.shm_name_data)
            self.frame = np.ndarray(self.frame_shape, dtype=self.frame_dtype, buffer=self.shm.buf)
        except Exception as e:
            print(f"Error attaching SHM: {e}")
            QTimer.singleShot(0, QApplication.instance().quit)

    def _init_timer(self):
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self._update)
        self.set_fps(QT_TIMER_INTERVAL)

    def set_fps(self, fps):
        if fps > 0:
            self.timer.setInterval(max(1, int(1000 / fps)))
            print(f"{self.__class__.__name__} FPS: {fps}")

    def _update(self):
        if self.frame is None: return
        self.fps.count_frame()
        if self.fps.able_to_calculate():
            print(f"{self.__class__.__name__} FPS: {self.fps.calculate():.2f}")
        self.render()

    def render(self):
        raise NotImplementedError

    def showEvent(self, e):
        self.timer.start()

    def hideEvent(self, e):
        self.timer.stop()

    def closeEvent(self, e):
        self._cleanup()

    def _cleanup(self):
        if self.timer.isActive(): self.timer.stop()
        if self.shm: self.shm.close()
        self.frame = None


class OpenGLVideoWidget(BaseVideoWidget, QOpenGLWidget):
    def __init__(self, shm_name, shape, dtype, stop_event, parent=None):
        QOpenGLWidget.__init__(self, parent)
        BaseVideoWidget.__init__(self, shm_name, shape, dtype, stop_event)

        # Настройка формата поверхности для OpenGL
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)  # Укажите версию OpenGL, поддерживающую шейдеры
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setDepthBufferSize(24)
        fmt.setSwapInterval(0)  # Отключить V-Sync
        self.setFormat(fmt)

        self.rgb_frame = np.zeros((shape[0], shape[1], 3), np.uint8)
        self.tex = None
        self.shader = None
        self.vao = None
        self.vbo = None

    def initializeGL(self):
        """Вызывается, когда OpenGL-контекст активен"""
        glClearColor(0.0, 0.0, 0.0, 1.0)
        try:
            self.shader = shaders.compileProgram(
                shaders.compileShader(VERTEX_SHADER_SOURCE, GL_VERTEX_SHADER),
                shaders.compileShader(FRAGMENT_SHADER_SOURCE, GL_FRAGMENT_SHADER)
            )
            self._init_buffers()
            self._init_texture()
        except Exception as e:
            print(f"GL error: {e}")
            QTimer.singleShot(0, QApplication.instance().quit)

    def _init_buffers(self):
        vertices = np.array([
            1, 1, 0, 1, 0,
            1, -1, 0, 1, 1,
            -1, -1, 0, 0, 1,
            -1, 1, 0, 0, 0
        ], np.float32)

        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)

        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, False, 20, None)
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 2, GL_FLOAT, False, 20, ctypes.c_void_p(12))

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

    def _init_texture(self):
        self.tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self.frame_width, self.frame_height, 0, GL_RGB, GL_UNSIGNED_BYTE, None)
        glBindTexture(GL_TEXTURE_2D, 0)

    def paintGL(self):
        if not all(i is not None for i in [self.shader, self.tex, self.frame]):
            return

        try:
            cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB, dst=self.rgb_frame)
            glBindTexture(GL_TEXTURE_2D, self.tex)
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.frame_width, self.frame_height, GL_RGB, GL_UNSIGNED_BYTE, self.rgb_frame)
            glBindTexture(GL_TEXTURE_2D, 0)
        except Exception as e:
            print(f"GL update error: {e}")

        glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(self.shader)
        glBindTexture(GL_TEXTURE_2D, self.tex)
        glUniform1i(glGetUniformLocation(self.shader, "ourTexture"), 0)
        glBindVertexArray(self.vao)
        glDrawArrays(GL_TRIANGLE_FAN, 0, 4)
        glBindVertexArray(0)
        glUseProgram(0)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)

    def render(self):
        self.update()

    def _cleanup(self):
        self.makeCurrent()
        if self.tex:
            glDeleteTextures([self.tex])
        if self.vbo:
            glDeleteBuffers(1, [self.vbo])
        if self.vao:
            glDeleteVertexArrays(1, [self.vao])
        if self.shader:
            glDeleteProgram(self.shader)
        self.doneCurrent()
        BaseVideoWidget._cleanup(self)


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
        if self.frame is None: return
        try:
            h, w, c = self.frame.shape
            img = QImage(self.frame.data, w, h, 3 * w, QImage.Format.Format_BGR888)
            self.label.setPixmap(QPixmap.fromImage(img))
        except Exception as e:
            print(f"Label error: {e}")


class MainWindow(QMainWindow):
    def __init__(self, shm_name, shape, dtype, stop_event):
        super().__init__()
        self.stop_event = stop_event
        self.setWindowTitle("Веб-камера")
        self.resize(shape[1], shape[0])
        self.setMinimumSize(320, 240)

        self.stack = QStackedWidget(self)
        self.opengl = OpenGLVideoWidget(shm_name, shape, dtype, stop_event, self)
        self.label = QLabelVideoWidget(shm_name, shape, dtype, stop_event, self)
        self.stack.addWidget(self.opengl)
        self.stack.addWidget(self.label)
        self.setCentralWidget(self.stack)

        self.fps = 30
        self.opengl.set_fps(self.fps)
        self.label.set_fps(self.fps)
        self._create_menu()

    def _create_menu(self):
        menu = self.menuBar()
        file_menu = menu.addMenu("&Файл")
        exit_action = QAction("&Выход", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menu.addMenu("&Вид")
        self.opengl_act = QAction("OpenGL", self, checkable=True, checked=True)
        self.label_act = QAction("QLabel", self, checkable=True)
        group = QActionGroup(self)
        group.addAction(self.opengl_act)
        group.addAction(self.label_act)
        view_menu.addAction(self.opengl_act)
        view_menu.addAction(self.label_act)
        self.opengl_act.triggered.connect(lambda: self.stack.setCurrentIndex(0))
        self.label_act.triggered.connect(lambda: self.stack.setCurrentIndex(1))

        set_fps = QAction("Set FPS", self)
        set_fps.triggered.connect(self.set_fps)
        view_menu.addAction(set_fps)

    def set_fps(self):
        fps, ok = QInputDialog.getInt(self, "FPS", "Enter FPS:", self.fps, 1, 999999)
        if ok:
            self.fps = fps
            self.opengl.set_fps(fps)
            self.label.set_fps(fps)

    def closeEvent(self, e): self.stop_event.set()


def signal_handler(signum, frame, stop_event=None):
    if stop_event: stop_event.set()
    if QApplication.instance(): QApplication.instance().quit


def capture_process(shm_name, shape, dtype, stop_event):
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, stop_event))
    try:
        shm = mp.shared_memory.SharedMemory(name=shm_name)
        frame = np.ndarray(shape, dtype=dtype, buffer=shm.buf)
        cap = cv2.VideoCapture(CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, shape[1])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, shape[0])
        cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)

        while not stop_event.is_set():
            ret, current = cap.read()
            if not ret or current is None:
                time.sleep(0.001)
                continue
            if current.shape[:2] != (shape[0], shape[1]):
                current = cv2.resize(current, (shape[1], shape[0]))
            np.copyto(frame, current)
    except Exception as e:
        print(f"Capture error: {e}")
    finally:
        stop_event.set()
        if 'cap' in locals() and cap.isOpened(): cap.release()
        if 'shm' in locals(): shm.close()


def display_process(shm_name, shape, dtype, stop_event):
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, stop_event))
    app = QApplication(sys.argv)
    try:
        win = MainWindow(shm_name, shape, dtype, stop_event)
        win.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Display error: {e}")
        stop_event.set()


if __name__ == "__main__":
    mp.freeze_support()
    print("Starting...")

    shape, dtype, size = get_frame_props(CAMERA_INDEX)
    if shape is None: sys.exit(1)

    stop_event = mp.Event()
    shm_data_name = f"{SHM_PREFIX}_data"
    shm = None

    try:
        shm = SharedMemory(name=shm_data_name, create=True, size=int(size))
        print(f"SHM {shm_data_name} created")
    except FileExistsError:
        try:
            existing = SharedMemory(name=shm_data_name)
            existing.unlink()
            existing.close()
            shm = mp.shared_memory.SharedMemory(name=shm_data_name, create=True, size=int(size))
            print("SHM recreated")
        except Exception as e:
            print(f"SHM error: {e}")
            sys.exit(1)

    args = (shm_data_name, shape, dtype, stop_event)
    capture = mp.Process(target=capture_process, args=args, name="Capture")
    display = mp.Process(target=display_process, args=args, name="Display")
    capture.start()
    display.start()

    try:
        display.join()
        stop_event.set()
        capture.join(timeout=5)
        if capture.is_alive():
            capture.terminate()
    except KeyboardInterrupt:
        stop_event.set()
        display.join(timeout=3)
        capture.join(timeout=5)
        if display.is_alive(): display.terminate()
        if capture.is_alive(): capture.terminate()

    finally:
        if shm:
            try:
                shm.unlink()
                print("SHM unlinked")
            except FileNotFoundError:
                pass
            shm.close()
        print("Exit")
        sys.exit(0)