import cv2
import asyncio
import websockets
import numpy as np

def numpy_to_bytes(arr: np.array) -> str:
    arr_dtype = bytearray(str(arr.dtype), 'utf-8')
    arr_shape = bytearray(','.join([str(a) for a in arr.shape]), 'utf-8')
    sep = bytearray('|', 'utf-8')
    arr_bytes = arr.ravel().tobytes()
    to_return = arr_dtype + sep + arr_shape + sep + arr_bytes
    return to_return

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
            #frame_str = cv2.imencode('.jpg', frame)[1].tostring()
            frame_str = numpy_to_bytes(frame)
            # Отправка кадра всем клиентам через веб-сокеты
            await asyncio.gather(*[ws.send(frame_str) for ws in self.websockets])

    def start(self):
        start_server = websockets.serve(self.serve, 'localhost', 8000)

        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()

server = WebcamServer()
server.start()
