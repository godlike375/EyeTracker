from operator import rshift
import cv2 as cv
import numpy as np
import mediapipe as mp
import sys

from pygad import pygad

from tracker.utils.coordinates import Point
from tracker.utils.image_processing import draw_text
from tracker.utils.shared_objects import SharedVector

sys.path.append('..')
from tracker.utils.fps import FPSLimiter
mp_face_mesh = mp.solutions.face_mesh


FACE_MESH_POINTS = 468
TOTAL_MESH_POINTS = 478
RIGHT_PUPIL = 473
LEFT_PUPIL = 468

#cap = cv.VideoCapture(r"C:\Users\godlike\Desktop\макаки2\video_2024-06-25_18-03-25.mp4")
cap = cv.VideoCapture(1)
fps = FPSLimiter(30)
reset_timer = FPSLimiter(15)

cv.namedWindow(winname='choose point', flags=cv.WINDOW_NORMAL)


def center_of_points(points):
    """Вычисляет центр множества точек"""
    return np.mean(points, axis=0)


def distance(a: np.ndarray, b: np.ndarray):
    return np.linalg.norm(a - b)


def similarity(a, b):
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    return dot_product / (norm_a * norm_b)

def normalized_vec(v):
    return v / np.linalg.norm(v)


top_face = 10
bottom_face = 152
left_face = 234
right_face = 454

right_of_right = 359  # 446
left_of_right = 414
top_of_right = 257  # 443
bottom_of_right = 374


iris_mm = 11.7
camera_fov_mm = 0.75
frame_width = 480
iris_zero_depth = iris_mm / camera_fov_mm * frame_width

def cam_relative_Z(iris_left, iris_right, point_z):
    iris_width = abs(iris_left[0] - iris_right[0])
    right_iris_distance = iris_zero_depth / iris_width
    dist_width = distance(iris_right, iris_left)
    dist_per_pixel = dist_width / iris_width
    #mm_by_1_step = dist_width / dist_per_pixel / iris_mm

    point_depth_pixels = (iris_left[2] - point_z)
    return right_iris_distance / camera_fov_mm - point_depth_pixels



started = False

RECORD_FRAMES = 555
RECORD_FACE_POINTS_INDICIES = np.array([right_of_right, left_of_right, top_of_right, bottom_of_right,
                                   389, 356, 454])
RECORD_ALL_POINTS_INDICIES = np.append(RECORD_FACE_POINTS_INDICIES, np.array([RIGHT_PUPIL, 476, 474]))

num_frame = 0

recorded_mesh_points = []
best_avg_fitness = -2
best_yet_solution = None
ga_instance = None


def fit_ga(recorded_points: list[np.ndarray], height: int, width: int) -> np.ndarray:
    global best_avg_fitness, ga_instance, best_yet_solution
    gene_space = [{'low': -2.65, 'high': 7.25} for _ in range(FACE_MESH_POINTS)]  # Коэффициенты для каждой из точек mesh

    def fitness_function(ga_instance, solution, solution_idx):
        global best_avg_fitness, best_yet_solution
        similarities = []
        for mesh_coords in recorded_points:
            pc = mesh_coords[RIGHT_PUPIL]
            #mesh_coords = mesh_coords[RECORD_ALL_POINTS_INDICIES]
            mesh_coords = mesh_coords[:FACE_MESH_POINTS]
            go = np.sum(mesh_coords * solution[:, np.newaxis], axis=0) / np.sum(solution)
            sc = np.array([width / 2, height / 2, 0])

            sc_pc_vector = sc - pc
            pc_go_vector = pc - go

            # Косинусное расстояние между нормализованными векторами
            sim = similarity(sc_pc_vector, pc_go_vector)
            similarities.append(sim)
        avg_fitness = np.mean(similarities)
        if best_avg_fitness < avg_fitness:
            best_yet_solution = solution
            best_avg_fitness = avg_fitness
            print(avg_fitness, ga_instance.generations_completed, solution_idx)

        return similarities

    if ga_instance is None:
        ga_instance = pygad.GA(gene_space=gene_space,
                               num_generations=3500,
                               num_parents_mating=4,
                               fitness_func=fitness_function,
                               sol_per_pop=6,
                               num_genes=FACE_MESH_POINTS,
                               init_range_low=-2.65,
                               init_range_high=7.25,
                               parallel_processing=['thread', None])
                               # mutation_percent_genes=[70, 35],
                               # mutation_type="adaptive")
    else:
        ga_instance.num_generations = 300

    ga_instance.run()
    ga_instance.save('ga_result.pickle')
    best = ga_instance.best_solution(ga_instance.last_generation_fitness)

    return best[0] if np.mean(best[1]) > best_avg_fitness else best_yet_solution

best = None

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
            z_coordinates = mesh_points[:, 2]
            mesh_points[:, 2] = np.array([cam_relative_Z(mesh_points[476], mesh_points[474], z) for z in z_coordinates])

            if started:
                if num_frame < RECORD_FRAMES and ga_instance is None:
                    num_frame += 1
                    recorded_mesh_points.append(mesh_points)
                else:
                    started = False
                    num_frame = 0
                    best = fit_ga(recorded_mesh_points, img_h, img_w)
                    recorded_mesh_points.clear()



            # for i, cords in enumerate(mesh_points):
            #     cy = int(cords[1])
            #     cx = int(cords[0])
            #     cv.circle(frame, (cx, cy), 1, (205, 0, 255), 1, cv.LINE_AA)
            #
            #     draw_text(frame, str(i), Point(cx, cy), 0.26)

            pupil = mesh_points[RIGHT_PUPIL]


            # threshold = 1
            # print(abs(t_f[0] - b_f[0]), abs(l_f[1] - r_f[1]), abs(t_f[2] - b_f[2]), abs(l_f[2] - r_f[2]))
            # if abs(t_f[0] - b_f[0]) < threshold and abs(l_f[1] - r_f[1]) < threshold\
            #         and abs(t_f[2] - b_f[2]) < threshold and abs(l_f[2] - r_f[2]) < threshold:
            #     np.save('face_model.npy', mesh_points)

            if best is not None:
                origin = np.sum(mesh_points[:FACE_MESH_POINTS] * best[:, np.newaxis], axis=0) / np.sum(best)


                end = (pupil - origin) * 6 + origin

                frame = cv.circle(frame, (int(pupil[0]), int(pupil[1])), 2, (0, 255, 0), 1, cv.LINE_AA)
                frame = cv.circle(frame, (int(origin[0]), int(origin[1])), 2, (0, 225, 245), 1, cv.LINE_AA)
                frame = cv.line(frame, (int(origin[0]), int(origin[1])),
                                (int(end[0]), int(end[1])), (0, 94, 255), 2)


            max_depth = mesh_points[:, 2].max()
            min_depth = mesh_points[:, 2].min()
            current_range = max_depth - min_depth
            step = 255 / current_range
            for i, cords in enumerate(mesh_points):
                cy = int(cords[1])
                cx = int(cords[0])
                depth_color = 255 - int((cords[2] - min_depth) * step)
                cv.circle(frame, (cx, cy), 1, (depth_color // 2, depth_color // 3, depth_color), 1, cv.LINE_AA)

                #draw_text(frame, str(i), Point(cx, cy), 0.26)

        # if reset_timer.able_to_execute():
        #     print(rr[2])
        #     face_mesh.reset()

        frame = cv.resize(frame, (1100, 620))
        cv.imshow('choose point', frame)
        key = cv.waitKey(1)
        if key ==ord('q'):
            face_mesh.reset()

        if key ==ord('s'):
            if not started:
                started = True


cap.release()
cv.destroyAllWindows()