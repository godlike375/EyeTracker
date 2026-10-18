import numpy as np
import cv2

class MacaqueTracker:
    def __init__(self):
        self.points = {} # ID точки: [x, y]
        self.initial_templates = {} # Эталонные изображения
        self.current_templates = {} # Адаптивные шаблоны
        self.velocities = {} # Векторы скорости для инерции
        self.win = 24 # Размер окна для шаблона

    def add_target(self, frame, x, y, label):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        x, y = int(x), int(y)
        patch = gray[y-self.win//2 : y+self.win//2, x-self.win//2 : x+self.win//2]
        if patch.shape == (self.win, self.win):
            self.points[label] = np.array([x, y], dtype=np.float32)
            self.initial_templates[label] = patch
            self.current_templates[label] = patch
            self.velocities[label] = np.array([0, 0], dtype=np.float32)

    def update(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        new_positions = {}

        for label, pos in self.points.items():
            # 1. Предсказание (инерция - помогает при быстрых рывках макаки)
            predicted_pos = pos + self.velocities[label]

            # 2. Поиск в локальной области вокруг предсказанной точки
            search_area_size = 50
            x1 = int(max(0, predicted_pos[0] - search_area_size//2))
            y1 = int(max(0, predicted_pos[1] - search_area_size//2))
            search_roi = gray[y1 : y1+search_area_size, x1 : x1+search_area_size]

            if search_roi.shape[0] < self.win or search_roi.shape[1] < self.win:
                continue

            # Сравниваем с текущим (адаптивным) шаблоном
            res = cv2.matchTemplate(search_roi, self.current_templates[label], cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            # Эвристика: порог уверенности 0.7 (с учетом мимики макаки)
            if max_val > 0.7:
                new_x = max_loc[0] + x1 + self.win//2
                new_y = max_loc[1] + y1 + self.win//2
                new_pos = np.array([new_x, new_y], dtype=np.float32)

                # Обновляем скорость (затухание 0.5)
                self.velocities[label] = (new_pos - pos) * 0.8
                self.points[label] = new_pos

                # Адаптация шаблона: подмешиваем 10% нового вида (чтобы следить при повороте)
                new_patch = gray[int(new_y-self.win//2):int(new_y+self.win//2),
                            int(new_x-self.win//2):int(new_x+self.win//2)]
                if new_patch.shape == (self.win, self.win):
                    self.current_templates[label] = cv2.addWeighted(self.current_templates[label], 0.9, new_patch, 0.1, 0)
            else:
                # Точка скрыта (макака отвернулась или моргнула)
                # Продолжаем двигать точку по инерции, но замедляем её
                self.points[label] = predicted_pos
                self.velocities[label] *= 0.9

        return self.points


def resize_to_720p(frame, target_w=1280, target_h=720):
    """Ресайз кадра до 1280x720 с сохранением пропорций (letterbox)."""
    h, w = frame.shape[:2]
    scale = min(target_w / w, target_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    # Создаём холст 1280x720 и центрируем на нём кадр
    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    x_off = (target_w - new_w) // 2
    y_off = (target_h - new_h) // 2
    canvas[y_off:y_off + new_h, x_off:x_off + new_w] = resized
    return canvas


def run_macaque_tracker(video_path):
    tracker = MacaqueTracker()
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print("Ошибка: Не удалось открыть видео.")
        return

    # Читаем первый кадр для выбора точек
    ret, frame = cap.read()
    if not ret:
        return

    # Ресайз первого кадра до 1280x720
    frame = resize_to_720p(frame)

    selected_points = []

    # Функция обработки кликов мыши
    def select_points(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            selected_points.append((x, y))
            # Рисуем временный маркер
            cv2.circle(frame_copy, (x, y), 5, (0, 255, 0), -1)
            cv2.imshow("Select Points - Press SPACE to Start", frame_copy)

    frame_copy = frame.copy()
    cv2.namedWindow("Select Points - Press SPACE to Start")
    cv2.setMouseCallback("Select Points - Press SPACE to Start", select_points)

    print("Инструкция: Кликните по морде макаки, затем нажмите ПРОБЕЛ.")

    while True:
        cv2.imshow("Select Points - Press SPACE to Start", frame_copy)
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' '): # Пробел для завершения выбора
            break
        elif key == 27: # ESC для выхода
            cap.release()
            cv2.destroyAllWindows()
            return

    # Регистрируем все выбранные точки в трекере
    for i, (x, y) in enumerate(selected_points):
        tracker.add_target(frame, x, y, label=f"point_{i}")

    cv2.destroyWindow("Select Points - Press SPACE to Start")

    # ОСНОВНОЙ ЦИКЛ ОБРАБОТКИ
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Ресайз каждого кадра до 1280x720
        frame = resize_to_720p(frame)

        # Обновляем координаты (используем эвристики инерции и шаблонов)
        tracked_points = tracker.update(frame)

        # Отрисовка результатов
        for label, pos in tracked_points.items():
            x, y = int(pos[0]), int(pos[1])
            # Рисуем точку
            cv2.circle(frame, (x, y), 4, (0, 255, 255), -1)
            # Рисуем подпись (Label)
            cv2.putText(frame, label, (x+5, y-5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        cv2.imshow("Macaque Tracking (Press Q to quit)", frame)

        if cv2.waitKey(20) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


# Запуск (укажите путь к вашему видео)
#run_macaque_tracker(r"C:\Users\Admin\Downloads\Telegram Desktop\D0000026V00002.AVI")
run_macaque_tracker(r"C:\Users\Admin\Videos\iVCam\20260107210058.mp4")