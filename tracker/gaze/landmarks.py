from operator import rshift
import cv2 as cv
import numpy as np
import mediapipe as mp
import sys

from tracker.utils.coordinates import Point
from tracker.utils.image_processing import draw_text
from tracker.utils.shared_objects import SharedVector

sys.path.append('..')
from tracker.utils.fps import FPSLimiter
mp_face_mesh = mp.solutions.face_mesh
LEFT_EYE =[ 362, 382, 381, 380, 374, 373, 390]#, 249, 263, 466, 388, 387, 386, 385,384, 398 ]
# right eyes indices
RIGHT_EYE=[ 33, 7, 163, 144, 145, 153, 154, 155]#, 133, 173, 157, 158, 159, 160, 161 , 246 ]
RIGHT_IRIS = [474, 475, 476, 477] # 473
LEFT_IRIS = [469, 470, 471, 472] # 468
#cap = cv.VideoCapture(r"C:\Users\godlike\Desktop\макаки2\video_2024-06-25_18-03-25.mp4")
cap = cv.VideoCapture(1)
fps = FPSLimiter(30)
reset_timer = FPSLimiter(15)

cv.namedWindow(winname='choose point', flags=cv.WINDOW_NORMAL)

mesh_points = []

def out_point(event, x, y, flags, param):
    if event == cv.EVENT_LBUTTONDOWN:
        indexed_points = [(i, point) for i, point in enumerate(mesh_points)]
        closest = list(sorted(indexed_points, key=lambda p: abs(p[1][0]-x) + abs(p[1][1] - y)))[0]
        print(closest[0])

cv.setMouseCallback('choose point', out_point)


def plane_from_points(points):
    """
    Вычисляет уравнение плоскости по 4 точкам.
    Возвращает коэффициенты A, B, C, D уравнения Ax + By + Cz + D = 0
    """
    p1, p2, p3 = points
    v1 = p2 - p1
    v2 = p3 - p1
    normal = np.cross(v1, v2)
    A, B, C = normal
    D = -np.dot(normal, p1)
    return A, B, C, D


def center_of_points(points):
    """Вычисляет центр множества точек"""
    return np.mean(points, axis=0)


def ray_end_point(points, distance, center):
    """
    Вычисляет конечную точку луча, ортогонального центру плоскости,
    на заданном расстоянии
    """
    # Вычисляем уравнение плоскости
    A, B, C, D = plane_from_points(points)
    normal = np.array([A, B, C])

    # Нормализуем вектор нормали
    normal_unit = normal / np.linalg.norm(normal)

    # Вычисляем конечную точку луча
    end_point = center + distance * normal_unit

    return end_point

mesh: list[SharedVector] = [SharedVector('f', -1) for _ in range(478)]

with mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.000000,
    min_tracking_confidence=0.0000001
) as face_mesh:
    while True:
        if not fps.able_to_execute():
            fps.throttle()
        ret, frame = cap.read()
        if not ret:
            break
        rgb_frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
        img_h, img_w = frame.shape[:2]
        results = face_mesh.process(rgb_frame)
        if results.multi_face_landmarks:
            mesh_points=np.array([np.multiply([p.x, p.y, p.z], [img_w, img_h, img_w])
                                  for p in results.multi_face_landmarks[0].landmark])

            for i, p in enumerate(mesh_points):
                mesh[i].array[:] = p[:]
            # print(mesh_points.shape)
            #frame = cv.polylines(frame, [mesh_points[LEFT_EYE]], True, (0,255,0), 1, cv.LINE_AA)
            #frame = cv.polylines(frame, [mesh_points[RIGHT_EYE]], True, (0,255,0), 1, cv.LINE_AA)
            #cv.circle(frame, center_left, 1, (255,0,255), 2, cv.LINE_AA)
            #cv.circle(frame, center_right, 1, (255, 0, 255), 2, cv.LINE_AA)
            # for i in mesh_points[LEFT_IRIS[:1]]:
            #     cv.circle(frame, i[:2], 1, (0, 255, 255), 2, cv.LINE_AA)
            # for i in mesh_points[RIGHT_IRIS[:1]]:
            #     cv.circle(frame, i[:2], 1, (0, 255, 255), 2, cv.LINE_AA)

            # right_of_right = 263
            # left_of_right = 362
            # top_of_right = 386
            # bottom_of_right = 374

            # right_of_right = 265
            # left_of_right = 463
            # top_of_right = 475 # 257
            # bottom_of_right = 253

            right_of_right = 265 # 446
            left_of_right = 464
            top_of_right = 257 # 443
            bottom_of_right = 374

            right_of_left = 133
            left_of_left = 33
            top_of_left = 159
            bottom_of_left = 145

            right_pupil = 473
            left_pupil = 468

            top_face = 10
            bottom_face = 152

            LEFT_EYE = [362, 382, 381, 380, 374, 373, 390]  # , 249, 263, 466, 388, 387, 386, 385,384, 398 ]
            # right eyes indices
            RIGHT_EYE = [33, 7, 163, 144, 145, 153, 154, 155]  # , 133, 173, 157, 158, 159, 160, 161 , 246 ]
            #frame = cv.circle(frame, mesh_points[1], 1, (0, 0, 255), 2, cv.LINE_AA)
            # for i in mesh_points[RIGHT_EYE]:
            #     cv.circle(frame, i, 1, (255, 255, 0), 2, cv.LINE_AA)
            # for i in mesh_points[LEFT_EYE]:
            #     cv.circle(frame, i, 1, (255, 255, 0), 2, cv.LINE_AA)

            # for i, cords in enumerate(mesh_points):
            #     cy = int(cords[1])
            #     cx = int(cords[0])
            #     cv.circle(frame, (cx, cy), 1, (205, 0, 255), 1, cv.LINE_AA)
            #
            #     draw_text(frame, str(i), Point(cx, cy), 0.26)

        # Пример использования
        #     points = np.array([mesh_points[i] for i in [right_of_right,
        #     left_of_right,
        #     top_of_right,
        #     bottom_of_right,]])
        #     rr = mesh_points[359]
        #     lr = mesh_points[441]
        #     tr = (mesh_points[336])
        #     br = mesh_points[349]
            rr = (mesh_points[398] + mesh_points[464]) / 2
            lr = (mesh_points[263] + mesh_points[359]) / 2
            tr = (mesh_points[336])
            br = (mesh_points[253] + mesh_points[254]) / 2
            points = [br, lr, rr]
            distance = -0.32
            center = (rr + lr) / 2
            pupil = mesh_points[right_pupil]

            start = (mesh_points[264] * 1.8 + mesh_points[139] * 0.7
                     + mesh_points[299] * 1.4 + mesh_points[253] * 6.3) / 10.2
            #start = ray_end_point(points, distance, center)


            end = (pupil - start) * 600 + start

            frame = cv.circle(frame, (int(pupil[0]), int(pupil[1])), 2, (0, 255, 0), 1, cv.LINE_AA)
            frame = cv.circle(frame, (int(start[0]), int(start[1])), 2, (0, 225, 245), 1, cv.LINE_AA)
            frame = cv.line(frame, (int(start[0]), int(start[1])),
                            (int(end[0]), int(end[1])), (245, 94, 98), 1)

        # if reset_timer.able_to_execute():
        #     print(rr[2])
        #     face_mesh.reset()

        frame = cv.resize(frame, (1100, 620))
        cv.imshow('choose point', frame)
        key = cv.waitKey(1)
        if key ==ord('q'):
            face_mesh.reset()
cap.release()
cv.destroyAllWindows()