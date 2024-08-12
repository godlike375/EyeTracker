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
LEFT_EYE =[ 362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385,384, 398 ]
# right eyes indices
RIGHT_EYE=[ 33, 7, 163, 144, 145, 153, 154, 155]#, 133, 173, 157, 158, 159, 160, 161 , 246 ]
RIGHT_IRIS = [474, 475, 476, 477] # 473
LEFT_IRIS = [469, 470, 471, 472] # 468
#cap = cv.VideoCapture(r"C:\Users\godlike\Desktop\макаки2\video_2024-06-25_18-03-25.mp4")
cap = cv.VideoCapture(0)
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


def center_of_points(points):
    """Вычисляет центр множества точек"""
    return np.mean(points, axis=0)


def distance(a: np.ndarray, b: np.ndarray):
    return np.linalg.norm(a - b)


right_of_right = 359  # 446
left_of_right = 414
top_of_right = 257  # 443
bottom_of_right = 374

top_face = 10
bottom_face = 152
left_face = 234
right_face = 454


face_model = np.load('face_model.npy')

c_l_o_r = (face_model[463])
c_r_o_r = (face_model[right_of_right] + face_model[466] * 2) / 3
c_t_o_r = (face_model[top_of_right] * 4 + face_model[443]) / 5
c_b_o_r = (face_model[253])
horizontal = distance(c_l_o_r, c_r_o_r)
vertical = distance(c_t_o_r, c_b_o_r)
right_eyeball_center_horizontal = np.array([c_l_o_r[0] + horizontal / 1.977,
                                c_l_o_r[1] - vertical / 4.53,
                                c_l_o_r[2] + horizontal / 4.54, 1])
right_eyeball_center_vertical = np.array([c_b_o_r[0],
                                c_b_o_r[1] - horizontal / 3.09,
                                c_b_o_r[2] + horizontal / 3.34, 1])

right_eyeball_center = (right_eyeball_center_horizontal + right_eyeball_center_vertical) / 2

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

            right_pupil = 473
            left_pupil = 468

            # for i, cords in enumerate(mesh_points):
            #     cy = int(cords[1])
            #     cx = int(cords[0])
            #     cv.circle(frame, (cx, cy), 1, (205, 0, 255), 1, cv.LINE_AA)
            #
            #     draw_text(frame, str(i), Point(cx, cy), 0.26)

            pupil = mesh_points[right_pupil]


            c_l_o_r = mesh_points[left_of_right]
            c_r_o_r = (mesh_points[right_of_right] + mesh_points[466] * 2) / 3
            c_t_o_r = (mesh_points[top_of_right] * 4 + mesh_points[443]) / 5
            c_b_o_r = (mesh_points[bottom_of_right] + mesh_points[253] * 4) / 5

            t_f = mesh_points[top_face]
            b_f = mesh_points[bottom_face]
            l_f = mesh_points[left_face]
            r_f = mesh_points[right_face]

            # threshold = 1
            # print(abs(t_f[0] - b_f[0]), abs(l_f[1] - r_f[1]), abs(t_f[2] - b_f[2]), abs(l_f[2] - r_f[2]))
            # if abs(t_f[0] - b_f[0]) < threshold and abs(l_f[1] - r_f[1]) < threshold\
            #         and abs(t_f[2] - b_f[2]) < threshold and abs(l_f[2] - r_f[2]) < threshold:
            #     np.save('face_model.npy', mesh_points)

            horizontal = distance(c_l_o_r, c_r_o_r)
            vertical = distance(c_t_o_r, c_b_o_r)

            l_o_r = np.array([-5, 0, 0])
            r_o_r = np.array([5, 0, 0])
            t_o_r = np.array([0, 2, 0])
            b_o_r = np.array([0, -2, 0])

            e_c = np.array([0, 0, 0.0, -10])
            #e_c = np.array([horizontal / 2, vertical / 2, 0])

            # success, transform_matrix, _ = cv.estimateAffine3D(np.asarray([l_o_r, r_o_r, t_o_r, b_o_r]),
            #                      np.asarray([c_l_o_r, c_r_o_r, c_t_o_r, c_b_o_r]))

            success, transform_matrix, inliners = cv.estimateAffine3D(face_model, mesh_points)

            if success:
                transformed_eye_center = np.dot(transform_matrix, right_eyeball_center)[:3]


                origin = transformed_eye_center


                end = (pupil - origin) * 90 + origin

                frame = cv.circle(frame, (int(pupil[0]), int(pupil[1])), 2, (0, 255, 0), 1, cv.LINE_AA)
                frame = cv.circle(frame, (int(origin[0]), int(origin[1])), 2, (0, 225, 245), 1, cv.LINE_AA)
                frame = cv.line(frame, (int(origin[0]), int(origin[1])),
                                (int(end[0]), int(end[1])), (0, 94, 255), 2)

            for i, cords in enumerate(face_model):
                cy = int(cords[1])
                cx = int(cords[0])
                cv.circle(frame, (cx, cy), 1, (205, 0, 255) if i not in LEFT_EYE else (255, 90, 0), 1, cv.LINE_AA)

            rbcx = right_eyeball_center[0]
            rbcy = right_eyeball_center[1]
            print(mesh_points[right_pupil][2])
            cv.circle(frame, (int(rbcx), int(rbcy)), 2, (0, 0, 0), 2, cv.LINE_AA)

                #draw_text(frame, str(i), Point(cx, cy), 0.26)

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