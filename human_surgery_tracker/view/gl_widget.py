import ctypes
import numpy as np
import cv2

from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import QTimer, Qt, QPoint
from OpenGL.GL import *
from OpenGL.GL import shaders

from tracker.camera import VideoAdapter
from tracker.utils.shared_objects import SharedBox, SharedPoint
from tracker.utils.coordinates import Point
from model.area_selector import AreaSelector, MAX_AREA_POINTS
from view.overlays import draw_detector_overlays, draw_roi_selection, draw_calibration_area, draw_laser_position, COLOR_LASER_VIRTUAL

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


class OpenGLVideoWidget(QOpenGLWidget):
    def __init__(self, adapter: VideoAdapter, main_window: 'MainWindow', roi_array, parent=None):
        super().__init__(parent)
        self.adapter = adapter
        self.main_window = main_window
        self.roi_array = roi_array
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.selection_start = None
        self.selection_end = None
        self.is_selecting = False
        self.area_selector = AreaSelector()
        self.calibration_preview = []
        self.area_selection_mode = False
        self.nudge_step = 1
        self.tex = None
        self.shader = None
        self.vao = None
        self.pbos = [None, None]
        self.pbo_idx = 0
        self._base_resolution = (adapter.width, adapter.height)
        self._rotate_degree = adapter.rotate_degree.value
        self.target_resolution = self._rotated_resolution()
        self._needs_realloc = False

    def _rotated_resolution(self):
        width, height = self._base_resolution
        if self._rotate_degree in (90, 270):
            return (height, width)
        return (width, height)

    def set_rotate_degree(self, degree: int):
        self._rotate_degree = degree
        new_resolution = self._rotated_resolution()
        if new_resolution != self.target_resolution:
            self.target_resolution = new_resolution
            self._needs_realloc = True
        self.update()

    def _allocate_texture(self):
        if self.tex is not None:
            glDeleteTextures([self.tex])
        self.tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB8, self.target_resolution[0], self.target_resolution[1],
                     0, GL_BGR, GL_UNSIGNED_BYTE, None)
        if self.pbos[0] is not None:
            glDeleteBuffers(2, self.pbos)
        self.pbos = glGenBuffers(2)
        for pbo in self.pbos:
            glBindBuffer(GL_PIXEL_UNPACK_BUFFER, pbo)
            glBufferData(GL_PIXEL_UNPACK_BUFFER, self.target_resolution[0] * self.target_resolution[1] * 3,
                         None, GL_STREAM_DRAW)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)

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
        self._allocate_texture()
        self._needs_realloc = False

    def paintGL(self):
        if self._needs_realloc and self.tex is not None:
            self._allocate_texture()
            self._needs_realloc = False

        frame = self.adapter.get_copy_video_frame()
        frame = draw_detector_overlays(frame, self.main_window.detector)

        if self.is_selecting and self.selection_start and self.selection_end:
            p1 = self._to_frame_coords(self.selection_start)
            p2 = self._to_frame_coords(self.selection_end)
            frame = draw_roi_selection(frame, p1, p2)

        if self.area_selector.points:
            frame = draw_calibration_area(frame, self.area_selector.to_tuples())

        if self.calibration_preview:
            frame = draw_calibration_area(frame, self.calibration_preview)

        if self.main_window.is_virtual_laser():
            laser_point = self.main_window.laser_screen_point()
            if laser_point is not None:
                frame = draw_laser_position(frame, (int(laser_point.x), int(laser_point.y)),
                                            COLOR_LASER_VIRTUAL)

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
        scale_x = self.target_resolution[0] / self.width()
        scale_y = self.target_resolution[1] / self.height()
        return (int(pt.x() * scale_x), int(pt.y() * scale_y))

    def begin_area_selection(self):
        self.area_selector.reset()
        self.area_selection_mode = True
        self.is_selecting = False
        self.selection_start = None
        self.selection_end = None
        self.setFocus()
        self.update()

    def cancel_area_selection(self):
        self.area_selection_mode = False
        self.area_selector.reset()
        self.update()

    def set_calibration_preview_point(self, index, x, y):
        while len(self.calibration_preview) <= index:
            self.calibration_preview.append(None)
        self.calibration_preview[index] = (int(x), int(y))
        self.calibration_preview = [p for p in self.calibration_preview if p is not None]
        self.update()

    def clear_calibration_display(self):
        self.area_selection_mode = False
        self.area_selector.reset()
        self.calibration_preview = []
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self.area_selection_mode:
                x, y = self._to_frame_coords(e.position().toPoint())
                complete = self.area_selector.add_point(Point(x, y))
                self.update()
                if complete:
                    self.area_selection_mode = False
                    self.main_window.on_area_points_selected(self.area_selector.points)
                return
            self.selection_start = e.position().toPoint()
            self.selection_end = e.position().toPoint()
            self.is_selecting = True

    def keyPressEvent(self, e):
        if self.area_selection_mode and self.area_selector.count:
            step = self.nudge_step
            key = e.key()
            moved = False
            if key == Qt.Key.Key_Left:
                moved = self.area_selector.nudge_last(-step, 0)
            elif key == Qt.Key.Key_Right:
                moved = self.area_selector.nudge_last(step, 0)
            elif key == Qt.Key.Key_Up:
                moved = self.area_selector.nudge_last(0, -step)
            elif key == Qt.Key.Key_Down:
                moved = self.area_selector.nudge_last(0, step)
            elif key == Qt.Key.Key_Escape:
                self.cancel_area_selection()
                return
            if moved:
                self.update()
                return
        super().keyPressEvent(e)

    def mouseMoveEvent(self, e):
        if self.area_selection_mode:
            return
        if self.is_selecting:
            self.selection_end = e.position().toPoint()

    def mouseReleaseEvent(self, e):
        if self.area_selection_mode:
            return
        if e.button() == Qt.MouseButton.LeftButton:
            self.is_selecting = False
            p1 = self._to_frame_coords(self.selection_start)
            p2 = self._to_frame_coords(self.selection_end)
            self.roi_array[:] = [min(p1[0], p2[0]), min(p1[1], p2[1]),
                                 max(p1[0], p2[0]), max(p1[1], p2[1])]
            self.main_window.on_roi_selected()
