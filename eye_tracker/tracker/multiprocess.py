import asyncio
import io
from multiprocessing.managers import BaseManager

import quick_queue
import websockets
import cv2
import json
import multiprocessing
from multiprocessing import Manager, Queue

from PIL import Image

from fps_counter import FPSCounter
#from object_tracker import ObjectTracker # предполагается, что этот модуль содержит класс трекера

def encode_image_to_jpeg(image):
    with io.BytesIO() as output_buffer:
        image.save(output_buffer, format="JPEG", quality=50)  # Сохраняем изображение в буфер в формате JPEG
        jpeg_data = output_buffer.getvalue()       # Получаем данные из буфера
    return jpeg_data


async def video_stream(frontend_socket, trackers_data):
    # Захват видео с веб-камеры
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    image = Image.fromarray(frame)
    frame_message = encode_image_to_jpeg(image)
    fps = FPSCounter()

    while True:

        #if not ret:
        #    continue

        # Конвертируем изображение в нужный формат для передачи
        #_, buffer = cv2.imencode('.jpg', frame)
        #frame_message = buffer.tobytes()

        # Отправка кадра на Frontend

        await frontend_socket.send(frame_message)
        if fps.able_to_calculate():
            print(f'backend: {fps.calculate()}')
        fps.frames += 1
        if trackers_data.empty():
            trackers_data.put(frame_message)

        #await asyncio.sleep(0.033)  # ~30 кадров в секунду

    cap.release()


def handle_tracker_process(trackers_data: quick_queue.QQueue, tracker_id):
    # Запуск процесса трекера
    fps = FPSCounter()
    while True:
        if fps.able_to_calculate():
            print(fps.calculate())

        if trackers_data.empty():
            continue
        else:
            data = trackers_data.get()
            fps.frames += 1
    #tracker = ObjectTracker(tracker_id, trackers_data[tracker_id], commands_queue)
    #tracker.run()


async def handle_frontend(websocket, path, trackers_data):
    # Создание процессов трекера
    tracker_processes = []
    for tracker_id in range(0, N):  # N - максимальное количество трекеров
        process = multiprocessing.Process(
            target=handle_tracker_process,
            args=(trackers_data, tracker_id)
        )
        process.start()
        tracker_processes.append(process)

    # Запуск передачи видео
    video_task = asyncio.create_task(video_stream(websocket, trackers_data))

    async for message in websocket:
        # Обработка команд от Frontend
        command = json.loads(message)
        if 'start_tracking' in command:
            tracker_id = command['tracker_id']
            #if tracker_id in commands_queues:
            #    commands_queues[tracker_id].put(command)  # Отправка команды конкретному трекеру

    # Завершение работы
    for process in tracker_processes:
        process.terminate()
    video_task.cancel()


    class MyManager(BaseManager):
        ...


if __name__ == '__main__':
    # Глобальное хранилище данных
    from quick_queue import QQueue

    BaseManager.register('QQueue', QQueue)
    BaseManager.register('Queue', Queue)
    BaseManager.register('dict', dict)
    manager = BaseManager()
    manager.start()
    trackers_data = Manager().dict()  # Словарь данных трекеров
    N = 1
    # Создание очередей данных
    #for i in range(0, N):  # N - максимальное количество трекеров
    quque = manager.QQueue()

    start_server = websockets.serve(
        lambda ws, path: handle_frontend(ws, path, quque),
        "localhost",
        5680
    )

    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
