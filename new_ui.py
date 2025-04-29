# -*- coding: utf-8 -*-
import sys
import multiprocessing
import multiprocessing.shared_memory
import time
import uuid
import signal
import numpy as np
import cv2

from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction

from OpenGL.GL import *
from OpenGL.GL import shaders

TARGET_RESOLUTION = (640, 480)
TARGET_FPS = 60
CAMERA_INDEX = 0
SHM_PREFIX = f"webcam_shm_gl_{uuid.uuid4()}"
QT_TIMER_INTERVAL = int(1000 / TARGET_FPS)

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
    """
    Attempts to get the properties of the first frame from the camera.
    Returns (frame_shape, frame_dtype_name, frame_size_bytes) or (None, None, None).
    """
    cap_check = cv2.VideoCapture(cam_index)
    if not cap_check.isOpened():
        print(f"Error: Cannot open camera {cam_index} for property check.")
        return None, None, None

    if target_resolution:
        cap_check.set(cv2.CAP_PROP_FRAME_WIDTH, target_resolution[0])
        cap_check.set(cv2.CAP_PROP_FRAME_HEIGHT, target_resolution[1])
        time.sleep(0.2) # Give camera time to adjust

    if target_fps:
        cap_check.set(cv2.CAP_PROP_FPS, target_fps)
        time.sleep(0.2) # Give camera time to adjust

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
# Removed new_frame_event from arguments
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

            # Check if the frame size is as expected, resize if necessary (and possible)
            if frame.shape[0] != target_height or frame.shape[1] != target_width:
                try:
                    frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_LINEAR)
                except cv2.error:
                     # If resize fails, skip this frame
                     continue

            try:
                # Copy the frame data to shared memory without synchronization
                np.copyto(shared_frame, frame)
                # Removed: new_frame_event.set()
            except ValueError:
                 # This might happen if the frame shape changes unexpectedly
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
        stop_event.set() # Ensure stop event is set on exit
        if cap and cap.isOpened():
            cap.release()
        if existing_shm_data:
            existing_shm_data.close()


# --- OpenGL Виджет для отображения видео ---
# Removed new_frame_event from arguments
class OpenGLVideoWidget(QOpenGLWidget):
    def __init__(self, shm_name_data, frame_shape, frame_dtype_name, stop_event, parent=None):
        super().__init__(parent)
        self.shm_name_data = shm_name_data
        self.frame_shape = frame_shape
        self.frame_height, self.frame_width, self.frame_channels = frame_shape
        self.frame_dtype = np.dtype(frame_dtype_name)
        self.stop_event = stop_event # Keep stop_event to know when to shut down

        self.shared_frame_bgr = None
        # Use zeros initially, updated with actual frame data later
        self.frame_rgb = np.zeros((self.frame_height, self.frame_width, 3), dtype=np.uint8)
        self.existing_shm_data = None
        self.texture_id = None
        self.shader_program = None
        self.vao = None
        self.vbo = None
        # We always assume a potential new frame is available if SHM is connected
        self.new_frame_available = False


        self._init_shm()
        self._init_timer()

        self.setMinimumSize(320, 240)

    def _init_shm(self):
        try:
            self.existing_shm_data = multiprocessing.shared_memory.SharedMemory(name=self.shm_name_data)
            # Create a NumPy array view into the shared memory buffer
            self.shared_frame_bgr = np.ndarray(self.frame_shape, dtype=self.frame_dtype, buffer=self.existing_shm_data.buf)
            self.new_frame_available = True # Assume data is potentially available after connecting
        except FileNotFoundError:
            print(f"Display process: SHM {self.shm_name_data} not found. Exiting.")
            # Use QTimer.singleShot to quit after the current event loop cycle,
            # otherwise calling quit() directly here might cause issues.
            QTimer.singleShot(0, QApplication.instance().quit)
        except Exception as e:
            print(f"Display process: Error attaching to SHM: {e}. Exiting.")
            QTimer.singleShot(0, QApplication.instance().quit)

    def _init_timer(self):
        # Timer triggers repaints at the desired FPS rate
        self.timer = QTimer(self)
        self.timer.setInterval(QT_TIMER_INTERVAL)
        # Connect the timer to the update function to trigger a repaint
        self.timer.timeout.connect(self.update) # Direct call to update()
        self.timer.start()

    # --- Методы QOpenGLWidget ---
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
            # Position        # Texture Coords (Flipped T)
             1.0,  1.0, 0.0,  1.0, 0.0, # Top Right
             1.0, -1.0, 0.0,  1.0, 1.0, # Bottom Right
            -1.0, -1.0, 0.0,  0.0, 1.0, # Bottom Left
            -1.0,  1.0, 0.0,  0.0, 0.0  # Top Left
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

        # Allocate memory for the texture
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self.frame_width, self.frame_height, 0, GL_RGB, GL_UNSIGNED_BYTE, None)

        glBindTexture(GL_TEXTURE_2D, 0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)


    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT)

        if self.shader_program is None or self.texture_id is None or self.shared_frame_bgr is None:
            # Cannot render without shader, texture, or shared memory
            return

        # Read from shared memory and update texture on every paint call
        # This is where frame tearing might occur
        try:
            cv2.cvtColor(self.shared_frame_bgr, cv2.COLOR_BGR2RGB, dst=self.frame_rgb)
            glBindTexture(GL_TEXTURE_2D, self.texture_id)
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.frame_width, self.frame_height, GL_RGB, GL_UNSIGNED_BYTE, self.frame_rgb)
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
        # Use glDrawArrays with GL_TRIANGLE_FAN for a simple quad
        glDrawArrays(GL_TRIANGLE_FAN, 0, 4)

        glBindVertexArray(0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glUseProgram(0)

    def _cleanupGL(self):
        # Ensure OpenGL context is current before deleting objects
        self.makeCurrent()
        if self.texture_id:
            glDeleteTextures([self.texture_id])
            self.texture_id = None
        if self.vbo:
            glDeleteBuffers(1, [self.vbo])
            self.vbo = None
        if self.vao:
            glDeleteVertexArrays(1, [self.vao])
            self.vao = None
        if self.shader_program:
            glDeleteProgram(self.shader_program)
            self.shader_program = None
        # Release the context
        self.doneCurrent()


    def _close_resources(self):
        if self.timer.isActive():
            self.timer.stop()
        if self.existing_shm_data:
            self.existing_shm_data.close()
        self.shared_frame_bgr = None
        self.frame_rgb = None

    def closeEvent(self, event):
        self._cleanupGL()
        self._close_resources()
        self.stop_event.set()
        super().closeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, shm_name_data, frame_shape, frame_dtype_name, stop_event):
        super().__init__()
        self.stop_event = stop_event

        self.setWindowTitle("Веб-камера")
        self.resize(frame_shape[1], frame_shape[0])
        self.setMinimumSize(320, 240)

        self._create_menu_bar()

        self.opengl_widget = OpenGLVideoWidget(
            shm_name_data, frame_shape, frame_dtype_name, stop_event, self
        )
        self.setCentralWidget(self.opengl_widget)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&Файл") # Use & for accelerator key

        exit_action = QAction("&Выход", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Выйти из приложения")
        exit_action.triggered.connect(self.close) # Connect to the window's close method
        file_menu.addAction(exit_action)

    def closeEvent(self, event):
        self.stop_event.set()
        # The central widget's closeEvent (OpenGLVideoWidget) is called automatically
        # before the main window is destroyed by Qt.
        event.accept() # Accept the close event


# --- Функция процесса отображения (точка входа) ---
def display_process(shm_name_data, frame_shape, frame_dtype_name, stop_event):
    def sigterm_handler(_signo, _stack_frame):
        stop_event.set()
        if QApplication.instance(): QApplication.instance().quit()
    # Register the signal handler for SIGTERM
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Enable High DPI scaling for better appearance on high-resolution displays
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)

    try:
        main_window = MainWindow(
            shm_name_data, frame_shape, frame_dtype_name, stop_event
        )
        main_window.show()

        exit_code = app.exec()
        stop_event.set()
        sys.exit(exit_code)
    except Exception as e:
        print(f"Display process: Unhandled exception in display_process: {e}")
        stop_event.set()
        sys.exit(1)


if __name__ == "__main__":
    # Required for multiprocessing on some platforms (e.g., Windows)
    multiprocessing.freeze_support()
    print("Starting application...")

    # Get initial camera properties to size SHM and windows correctly
    frame_shape, frame_dtype_name, frame_size_bytes = get_initial_frame_properties(
        CAMERA_INDEX, TARGET_RESOLUTION, TARGET_FPS
    )
    if frame_shape is None:
        print("Failed to get initial frame properties. Exiting.")
        sys.exit(1)

    stop_event = multiprocessing.Event() # Event to signal processes to stop

    # Setup Shared Memory
    shm_data_name = f"{SHM_PREFIX}_data"
    shared_memory_data = None
    try:
        shared_memory_data = multiprocessing.shared_memory.SharedMemory(
            name=shm_data_name, create=True, size=int(frame_size_bytes)
        )
        print(f"Shared memory {shm_data_name} created with size {frame_size_bytes} bytes.")
    except FileExistsError:
         print(f"SHM {shm_data_name} already exists. Attempting to unlink and recreate.")
         try:
              existing_shm = multiprocessing.shared_memory.SharedMemory(name=shm_data_name)
              existing_shm.unlink()
              existing_shm.close()
              shared_memory_data = multiprocessing.shared_memory.SharedMemory(
                   name=shm_data_name, create=True, size=int(frame_size_bytes)
              )
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
            process_capture.terminate() # Send SIGTERM (or equivalent)
            process_capture.join()      # Wait for termination
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
                # Unlinking removes the shared memory segment from the system
                shared_memory_data.unlink()
                print(f"Shared memory {shm_data_name} unlinked.")
            except FileNotFoundError:
                # This might happen if the display process unlinked it (less likely here, but good practice)
                pass
            except Exception as e:
                 print(f"Error unlinking shared memory {shm_data_name}: {e}")
            shared_memory_data.close()

        print("Application finished.")
        sys.exit(0)