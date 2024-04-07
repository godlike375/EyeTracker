import asyncio
import multiprocessing
import websockets

async def tracker_process(uri):
    async with websockets.connect(uri) as websocket:
        # Отправьте изображение на трекер для обработки и отслеживания
        await websocket.send("image bytes or processing result")
        # Получите команды для начала отслеживания объекта
        command = await websocket.recv()
        # Обработайте команду и выполняйте отслеживание
        # Отправьте результат отслеживания обратно в backend
        await websocket.send("tracking coordinates")

def start_tracker(uri):
    asyncio.run(tracker_process(uri))

if __name__ == "__main__":
    uri = "ws://localhost:5679"
    number_of_trackers = 1  # или любое другое количество трекеров, которое вы хотите запустить

    # Создание процессов для каждого трекера
    processes = [multiprocessing.Process(target=start_tracker, args=(uri,)) for _ in range(number_of_trackers)]

    # Запуск каждого процесса
    for process in processes:
        process.start()

    # Ждем завершения всех процессов
    for process in processes:
        process.join()
