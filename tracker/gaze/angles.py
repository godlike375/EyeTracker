import cv2
import mediapipe as mp
import numpy as np

mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(static_image_mode=False, max_num_faces=1, refine_landmarks=True,
                                  min_detection_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

cap = cv2.VideoCapture(1)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # Преобразование цвета изображения
    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Определение ключевых точек
    results = face_mesh.process(image)

    # Обратно в BGR для отображения
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    img_h, img_w = frame.shape[:2]
    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            #mp_drawing.draw_landmarks(image, face_landmarks, mp_face_mesh.FACEMESH_TESSELATION)

            mesh_points = np.array(
                [np.multiply([p.x, p.y, p.z], [img_w, img_h, img_w]).astype(int) for p in results.multi_face_landmarks[0].landmark])
            # Вывод Z координат для всех точек на лице
            #for idx, lm in enumerate(face_landmarks.landmark):
            #    x, y, z = lm.x, lm.y, lm.z
                #print(f"Landmark {idx}: Z = {z}")

            # Пример: Найденные координаты сделать в виде массива для дополнительной обработки
            coords = [lm for lm in mesh_points]

            # Найти минимальное (ближайшее) значение Z
            #closest_point = min(enumerate(coords), key=lambda x: x[1][2])
            #farthest_point = max(enumerate(coords), key=lambda x: x[1][2])
            #cv2.circle(image, (int(closest_point[1][0]), int(closest_point[1][1])), 1, (255, 0, 0), 2, cv2.INTER_AREA)
            for i in mesh_points:
                cv2.circle(image, (int(i[0]), int(i[1])), 1, (255, 0, 0), 2,
                           cv2.INTER_AREA)

            #print(f"Closest point index: {closest_point[0]}, Z: {closest_point[1]}")
            #print(f"Farthest point index: {farthest_point[0]}, Z: {farthest_point[1]}")

    cv2.imshow('Head Pose Estimation', image)

    if cv2.waitKey(5) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()