import cv2
import asyncio
import websockets

class WebcamServer:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.websockets = set()

    async def serve(self, websocket, path):
        self.websockets.add(websocket)
        while True:
            ret, frame = self.cap.read()
            # Обработка кадра (если необходимо)

            # Преобразование кадра в строку (для отправки через веб-сокет)
            frame_str = cv2.imencode('.jpg', frame)[1].tostring()

            # Отправка кадра всем клиентам через веб-сокеты
            await asyncio.gather(*[ws.send(frame_str) for ws in self.websockets])

    def start(self):
        start_server = websockets.serve(self.serve, 'localhost', 8000)

        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()

server = WebcamServer()
server.start()
