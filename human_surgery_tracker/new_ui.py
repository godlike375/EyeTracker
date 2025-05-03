# -*- coding: utf-8 -*-
import sys
import multiprocessing
import multiprocessing.shared_memory
import time
import uuid
import signal
import numpy as np
import cv2

from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QLabel, QVBoxLayout, QInputDialog, \
    QWidget
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap, QAction, QSurfaceFormat, QActionGroup

from OpenGL.GL import *
from OpenGL.GL import shaders

from tracker.utils.fps import FPSCounter

TARGET_RESOLUTION = (640, 480)
TARGET_FPS = 45 * 1.05
CAMERA_INDEX = 0
SHM_PREFIX = f"webcam_shm_gl_{uuid.uuid4()}"
QT_TIMER_INTERVAL = round(1000 / TARGET_FPS)

# --- Шейдеры ---
VERTEX_SHADER_SOURCE = """
#version 330 core
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec2 aTexCoord;

out vec2 TexCoord;

void main()
{
    gl_Position = vec4(aPos.x, aPos.y, aPos.z, 1.0);
    TexCoord = aTexCoord;
}
"""

FRAGMENT_SHADER_SOURCE = """
#version 330 core
out vec4 FragColor;

in vec2 TexCoord;

uniform sampler2D ourTexture;

void main()
{
    FragColor = texture(ourTexture, TexCoord);
}
"""


# --- Утилитарная функция для получения свойств кадра ---
def get_initial_frame_properties(cam_index, target_resolution=None, target_fps=None):
    cap_check = cv2.VideoCapture(cam_index)
    if not cap_check.isOpened():
        print(f"Error: Cannot open camera {cam_index} for property check.")
        return None, None, None

    if target_resolution:
        cap_check.set(cv2.CAP_PROP_FRAME_WIDTH, target_resolution[0])
        cap_check.set(cv2.CAP_PROP_FRAME_HEIGHT, target_resolution[1])
        time.sleep(0.2)

    if target_fps:
        cap_check.set(cv2.CAP_PROP_FPS, target_fps)
        time.sleep(0.2)

    frame_check = None
    attempts = 5
    for _ in range(attempts):
        ret_check, frame_check = cap_check.read()
        if ret_check and frame_check is not None:
            break
        time.sleep(0.1)

    if frame_check is None:
        print(f"Error: Could not read a frame from camera {cam_index} after {attempts} attempts.")
        cap_check.release()
        return None, None, None

    final_h, final_w = frame_check.shape[0], frame_check.shape[1]
    frame_shape = (final_h, final_w, frame_check.shape[2])
    frame_dtype = frame_check.dtype
    frame_dtype_name = frame_dtype.name
    frame_size_bytes = np.prod(frame_shape) * frame_dtype.itemsize

    cap_check.release()
    return frame_shape, frame_dtype_name, frame_size_bytes


# --- Процесс захвата видео ---
def capture_process(shm_name_data, frame_shape, frame_dtype_name, stop_event):
    def sigterm_handler(_signo, _stack_frame):
        stop_event.set()

    signal.signal(signal.SIGTERM, sigterm_handler)

    existing_shm_data = None
    cap = None

    try:
        existing_shm_data = multiprocessing.shared_memory.SharedMemory(name=shm_name_data)
        frame_dtype = np.dtype(frame_dtype_name)
        shared_frame = np.ndarray(frame_shape, dtype=frame_dtype, buffer=existing_shm_data.buf)

        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            print(f"Capture process: Cannot open camera {CAMERA_INDEX}")
            stop_event.set()
            return

        target_width, target_height = frame_shape[1], frame_shape[0]
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, target_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, target_height)
        cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)

        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.001)
                continue

            if frame.shape[0] != target_height or frame.shape[1] != target_width:
                try:
                    frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_LINEAR)
                except cv2.error:
                    continue

            try:
                np.copyto(shared_frame, frame)
            except ValueError:
                print("Capture process: Shape mismatch when copying frame to SHM. Stopping.")
                stop_event.set()
            except Exception as e:
                print(f"Capture process: Unexpected error copying frame: {e}. Stopping.")
                stop_event.set()

    except FileNotFoundError:
        print(f"Capture process: SHM {shm_name_data} not found. Exiting.")
    except Exception as e:
        print(f"Capture process: Unhandled exception: {e}")
    finally:
        stop_event.set()
        if cap and cap.isOpened():
            cap.release()
        if existing_shm_data:
            existing_shm_data.close()


# --- OpenGL Виджет для отображения видео ---
class OpenGLVideoWidget(QOpenGLWidget):
    def __init__(self, shm_name_data, frame_shape, frame_dtype_name, stop_event, parent=None):
        # Configure OpenGL format to disable V-Sync
        super().__init__(parent)
        fmt = QSurfaceFormat()
        fmt.setSwapInterval(0)  # Disable V-Sync
        #fmt.setRenderableType(QSurfaceFormat.OpenGLContextProfile)
        self.setFormat(fmt)


        self.shm_name_data = shm_name_data
        self.frame_shape = frame_shape
        self.frame_height, self.frame_width, self.frame_channels = frame_shape
        self.frame_dtype = np.dtype(frame_dtype_name)
        self.stop_event = stop_event

        self.shared_frame_bgr = None
        self.frame_rgb = np.zeros((self.frame_height, self.frame_width, 3), dtype=np.uint8)
        self.existing_shm_data = None
        self.texture_id = None
        self.shader_program = None
        self.vao = None
        self.vbo = None
        self.last_frame_time = time.time()

        self._init_shm()
        self._init_timer()

        self.setMinimumSize(320, 240)

    def _init_shm(self):
        try:
            self.existing_shm_data = multiprocessing.shared_memory.SharedMemory(name=self.shm_name_data)
            self.shared_frame_bgr = np.ndarray(self.frame_shape, dtype=self.frame_dtype,
                                               buffer=self.existing_shm_data.buf)
        except FileNotFoundError:
            print(f"Display process: SHM {self.shm_name_data} not found. Exiting.")
            QTimer.singleShot(0, QApplication.instance().quit)
        except Exception as e:
            print(f"Display process: Error attaching to SHM: {e}. Exiting.")
            QTimer.singleShot(0, QApplication.instance().quit)

    def _init_timer(self):
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)  # Use high-precision timer
        self.timer.setInterval(QT_TIMER_INTERVAL)
        self.fps = FPSCounter()
        self.timer.timeout.connect(self.update)
        # Timer starts in showEvent

    def set_fps(self, fps):
        if fps > 0:
            interval = int(1000 / fps)
            if interval < 1:
                interval = 1  # Prevent zero or negative intervals
            self.timer.setInterval(interval)
            print(f"OpenGL: Set FPS to {fps}, timer interval {interval} ms")
        else:
            print("Invalid FPS value. Must be greater than 0.")

    def initializeGL(self):
        glClearColor(0.0, 0.0, 0.0, 1.0)

        try:
            vertex_shader = shaders.compileShader(VERTEX_SHADER_SOURCE, GL_VERTEX_SHADER)
            fragment_shader = shaders.compileShader(FRAGMENT_SHADER_SOURCE, GL_FRAGMENT_SHADER)
            self.shader_program = shaders.compileProgram(vertex_shader, fragment_shader)
        except shaders.ShaderCompilationError as e:
            print(f"Display process: Shader compilation error: {e}")
            self.shader_program = None
            QTimer.singleShot(0, QApplication.instance().quit)
            return
        except Exception as e:
            print(f"Display process: Unexpected error during shader compilation: {e}")
            self.shader_program = None
            QTimer.singleShot(0, QApplication.instance().quit)
            return

        vertices = np.array([
            1.0, 1.0, 0.0, 1.0, 0.0,
            1.0, -1.0, 0.0, 1.0, 1.0,
            -1.0, -1.0, 0.0, 0.0, 1.0,
            -1.0, 1.0, 0.0, 0.0, 0.0
        ], dtype=np.float32)

        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)

        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 5 * vertices.itemsize, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 5 * vertices.itemsize, ctypes.c_void_p(3 * vertices.itemsize))
        glEnableVertexAttribArray(1)

        self.texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self.frame_width, self.frame_height, 0, GL_RGB, GL_UNSIGNED_BYTE, None)

        glBindTexture(GL_TEXTURE_2D, 0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)

    def paintGL(self):
        start_time = time.time()
        glClear(GL_COLOR_BUFFER_BIT)

        if self.shader_program is None or self.texture_id is None or self.shared_frame_bgr is None:
            return

        try:
            cv2.cvtColor(self.shared_frame_bgr, cv2.COLOR_BGR2RGB, dst=self.frame_rgb)
            glBindTexture(GL_TEXTURE_2D, self.texture_id)
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.frame_width, self.frame_height, GL_RGB, GL_UNSIGNED_BYTE,
                            self.frame_rgb)
            glBindTexture(GL_TEXTURE_2D, 0)
        except cv2.error:
            print("Display process: OpenCV error during color conversion.")
        except Exception as e:
            print(f"Display process: Unexpected error during texture update: {e}")

        glUseProgram(self.shader_program)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glUniform1i(glGetUniformLocation(self.shader_program, "ourTexture"), 0)

        glBindVertexArray(self.vao)
        glDrawArrays(GL_TRIANGLE_FAN, 0, 4)

        glBindVertexArray(0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glUseProgram(0)

        self.fps.count_frame()
        if self.fps.able_to_calculate():
            print(f"OpenGL FPS: {self.fps.calculate():.2f}")

        # Log frame rendering time for diagnostics
        frame_time_ms = (time.time() - start_time) * 1000
        if frame_time_ms > 5:  # Log if rendering takes significant time
            print(f"OpenGL: Frame rendering took {frame_time_ms:.2f} ms")

    def showEvent(self, event):
        self.timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event):
        self._cleanupGL()
        self._close_resources()
        super().closeEvent(event)

    def _cleanupGL(self):
        self.makeCurrent()
        if self.texture_id:
            glDeleteTextures([self.texture_id])
        if self.vbo:
            glDeleteBuffers(1, [self.vbo])
        if self.vao:
            glDeleteVertexArrays(1, [self.vao])
        if self.shader_program:
            glDeleteProgram(self.shader_program)
        self.doneCurrent()

    def _close_resources(self):
        if self.timer.isActive():
            self.timer.stop()
        if self.existing_shm_data:
            self.existing_shm_data.close()
        self.shared_frame_bgr = None
        self.frame_rgb = None


# --- QLabel Виджет для отображения видео ---
class QLabelVideoWidget(QWidget):
    def __init__(self, shm_name_data, frame_shape, frame_dtype_name, stop_event, parent=None):
        super().__init__(parent)
        self.shm_name_data = shm_name_data
        self.frame_shape = frame_shape
        self.frame_height, self.frame_width, self.frame_channels = frame_shape
        self.frame_dtype = np.dtype(frame_dtype_name)
        self.stop_event = stop_event

        self.shared_frame_bgr = None
        self.existing_shm_data = None
        self.fps = FPSCounter()

        self._init_shm()
        self._init_ui()
        self._init_timer()

    def _init_shm(self):
        try:
            self.existing_shm_data = multiprocessing.shared_memory.SharedMemory(name=self.shm_name_data)
            self.shared_frame_bgr = np.ndarray(self.frame_shape, dtype=self.frame_dtype,
                                               buffer=self.existing_shm_data.buf)
        except FileNotFoundError:
            print(f"Display process: SHM {self.shm_name_data} not found. Exiting.")
            QTimer.singleShot(0, QApplication.instance().quit)
        except Exception as e:
            print(f"Display process: Error attaching to SHM: {e}. Exiting.")
            QTimer.singleShot(0, QApplication.instance().quit)

    def _init_ui(self):
        self.label = QLabel(self)
        self.label.setScaledContents(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
        self.setMinimumSize(320, 240)

    def _init_timer(self):
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)  # Use high-precision timer
        self.timer.timeout.connect(self.update_frame)
        self.set_fps(30)

    def set_fps(self, fps):
        if fps > 0:
            interval = int(1000 / fps)
            if interval < 1:
                interval = 1
            self.timer.setInterval(interval)
            print(f"QLabel: Set FPS to {fps}, timer interval {interval} ms")
        else:
            print("Invalid FPS value. Must be greater than 0.")

    def update_frame(self):
        self.fps.count_frame()
        if self.fps.able_to_calculate():
            print(f"QLabel FPS: {self.fps.calculate():.2f}")
        if self.shared_frame_bgr is None:
            return
        try:
            height, width, channel = self.shared_frame_bgr.shape
            bytes_per_line = 3 * width
            qimage = QImage(self.shared_frame_bgr.data, width, height, bytes_per_line, QImage.Format.Format_BGR888)
            self.label.setPixmap(QPixmap.fromImage(qimage))
        except cv2.error:
            print("Display process: OpenCV error during color conversion.")
        except Exception as e:
            print(f"Display process: Unexpected error during frame update: {e}")

    def showEvent(self, event):
        self.timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event):
        self._close_resources()
        super().closeEvent(event)

    def _close_resources(self):
        if self.timer.isActive():
            self.timer.stop()
        if self.existing_shm_data:
            self.existing_shm_data.close()
        self.shared_frame_bgr = None


# --- Главное окно ---
class MainWindow(QMainWindow):
    def __init__(self, shm_name_data, frame_shape, frame_dtype_name, stop_event):
        super().__init__()
        self.stop_event = stop_event

        self.setWindowTitle("Веб-камера")
        self.resize(frame_shape[1], frame_shape[0])
        self.setMinimumSize(320, 240)

        self.stacked_widget = QStackedWidget(self)
        self.opengl_widget = OpenGLVideoWidget(shm_name_data, frame_shape, frame_dtype_name, stop_event, self)
        self.label_widget = QLabelVideoWidget(shm_name_data, frame_shape, frame_dtype_name, stop_event, self)
        self.stacked_widget.addWidget(self.opengl_widget)
        self.stacked_widget.addWidget(self.label_widget)
        self.setCentralWidget(self.stacked_widget)

        self.display_fps = 30
        self.opengl_widget.set_fps(self.display_fps)
        self.label_widget.set_fps(self.display_fps)

        self._create_menu_bar()

    def _create_menu_bar(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&Файл")
        exit_action = QAction("&Выход", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Выйти из приложения")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menu_bar.addMenu("&Вид")
        self.action_opengl = QAction("Use OpenGL", self)
        self.action_opengl.setCheckable(True)
        self.action_opengl.setChecked(True)
        self.action_label = QAction("Use QLabel", self)
        self.action_label.setCheckable(True)
        action_group = QActionGroup(self)
        action_group.addAction(self.action_opengl)
        action_group.addAction(self.action_label)
        action_group.setExclusive(True)
        view_menu.addAction(self.action_opengl)
        view_menu.addAction(self.action_label)
        self.action_opengl.triggered.connect(self.switch_to_opengl)
        self.action_label.triggered.connect(self.switch_to_label)

        set_fps_action = QAction("Set FPS", self)
        set_fps_action.triggered.connect(self.set_fps)
        view_menu.addAction(set_fps_action)

    def switch_to_opengl(self):
        self.stacked_widget.setCurrentIndex(0)

    def switch_to_label(self):
        self.stacked_widget.setCurrentIndex(1)

    def set_fps(self):
        fps, ok = QInputDialog.getInt(self, "Set FPS", "Enter FPS:", self.display_fps, 1, 10000)
        if ok:
            self.display_fps = fps
            self.opengl_widget.set_fps(fps)
            self.label_widget.set_fps(fps)

    def closeEvent(self, event):
        self.stop_event.set()
        event.accept()


# --- Функция процесса отображения (точка входа) ---
def display_process(shm_name_data, frame_shape, frame_dtype_name, stop_event):
    def sigterm_handler(_signo, _stack_frame):
        stop_event.set()
        if QApplication.instance():
            QApplication.instance().quit()

    signal.signal(signal.SIGTERM, sigterm_handler)

    app = QApplication(sys.argv)

    try:
        main_window = MainWindow(shm_name_data, frame_shape, frame_dtype_name, stop_event)
        main_window.show()
        exit_code = app.exec()
        stop_event.set()
        sys.exit(exit_code)
    except Exception as e:
        print(f"Display process: Unhandled exception in display_process: {e}")
        stop_event.set()
        sys.exit(1)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    print("Starting application...")

    frame_shape, frame_dtype_name, frame_size_bytes = get_initial_frame_properties(CAMERA_INDEX, TARGET_RESOLUTION,
                                                                                   TARGET_FPS)
    if frame_shape is None:
        print("Failed to get initial frame properties. Exiting.")
        sys.exit(1)

    stop_event = multiprocessing.Event()

    shm_data_name = f"{SHM_PREFIX}_data"
    shared_memory_data = None
    try:
        shared_memory_data = multiprocessing.shared_memory.SharedMemory(name=shm_data_name, create=True,
                                                                        size=int(frame_size_bytes))
        print(f"Shared memory {shm_data_name} created with size {frame_size_bytes} bytes.")
    except FileExistsError:
        print(f"SHM {shm_data_name} already exists. Attempting to unlink and recreate.")
        try:
            existing_shm = multiprocessing.shared_memory.SharedMemory(name=shm_data_name)
            existing_shm.unlink()
            existing_shm.close()
            shared_memory_data = multiprocessing.shared_memory.SharedMemory(name=shm_data_name, create=True,
                                                                            size=int(frame_size_bytes))
            print(f"Shared memory {shm_data_name} unlinked and recreated.")
        except Exception as e:
            print(f"Error handling existing SHM {shm_data_name}: {e}. Exiting.")
            sys.exit(1)
    except Exception as e:
        print(f"Error creating SHM: {e}. Exiting.")
        if shared_memory_data:
            shared_memory_data.close()
        sys.exit(1)

    capture_args = (shm_data_name, frame_shape, frame_dtype_name, stop_event)
    display_args = (shm_data_name, frame_shape, frame_dtype_name, stop_event)

    process_capture = multiprocessing.Process(target=capture_process, args=capture_args, name="CaptureProcess")
    process_display = multiprocessing.Process(target=display_process, args=display_args, name="DisplayProcess")

    process_capture.start()
    process_display.start()
    print("Capture and Display processes started.")

    try:
        process_display.join()
        print("Display process finished.")

        stop_event.set()
        print("Stop event set for capture process.")

        process_capture.join(timeout=5)
        if process_capture.is_alive():
            print("Capture process did not terminate gracefully, terminating it.")
            process_capture.terminate()
            process_capture.join()
        print("Capture process finished.")

    except KeyboardInterrupt:
        print("KeyboardInterrupt received. Setting stop event.")
        stop_event.set()
        process_display.join(timeout=3)
        process_capture.join(timeout=5)
        if process_display.is_alive():
            print("Display process did not terminate gracefully, terminating it.")
            process_display.terminate()
            process_display.join()
        if process_capture.is_alive():
            print("Capture process did not terminate gracefully, terminating it.")
            process_capture.terminate()
            process_capture.join()

    finally:
        if shared_memory_data:
            try:
                shared_memory_data.unlink()
                print(f"Shared memory {shm_data_name} unlinked.")
            except FileNotFoundError:
                pass
            except Exception as e:
                print(f"Error unlinking shared memory {shm_data_name}: {e}")
            shared_memory_data.close()

        print("Application finished.")
        sys.exit(0)