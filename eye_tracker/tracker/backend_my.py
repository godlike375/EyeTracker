import asyncio

import websockets
import io
import cv2
from PIL import Image
from websockets import WebSocketServerProtocol

from eye_tracker.tracker.fps_counter import FPSCounter


import imageio as iio

# works 2 times faster than imencode!
def encode_image_to_jpeg(image):
    with io.BytesIO() as output_buffer:
        image.save(output_buffer, format="JPEG", quality=50)  # Сохраняем изображение в буфер в формате JPEG
        jpeg_data = output_buffer.getvalue()       # Получаем данные из буфера
    return jpeg_data


class VideoCameraThread:
    def __init__(self):
        self.camera = cv2.VideoCapture(0)

        self.camera.set(cv2.CAP_PROP_FPS, 60)
        #self.ret, self.frame = self.camera.read()

    def __del__(self):
        self.camera.release()
        #self.camera.close()

    def get_frame(self) -> bytes:
        ret, frame = self.camera.read()
        image = Image.fromarray(frame)
        encoded = encode_image_to_jpeg(image)
        return encoded if ret else None
        #return cv2.imencode('.jpg', self.frame, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tobytes() #if ret else None


class WebSocketServer:
    def __init__(self):
        self.clients: set[WebSocketServerProtocol] = set()
        self.camera = VideoCameraThread()
        self.fps = FPSCounter()

    def start(self):
        websock_server = websockets.serve(self.websock_handler, "0.0.0.0", 5680)
        sock_server = asyncio.start_server(self.sock_handler, "0.0.0.0", 5679)
        asyncio.gather(*[websock_server, sock_server])
        asyncio.get_event_loop().run_forever()

    async def register(self, websocket):
        self.clients.add(websocket)

    async def unregister(self, websocket):
        self.clients.remove(websocket)

    async def send_to_clients(self, message):
        if self.fps.able_to_calculate():
            print(self.fps.calculate())

        self.fps.frames += 1
        # less CPU loading and 235 avg fps vs 255 in gathering
        #for client in self.clients:
        #    await asyncio.create_task(client.send(message))
        await asyncio.gather(*[client.send(message) for client in self.clients])

    async def stream_video(self):
        while True:
            frame = self.camera.get_frame()
            if frame:
                await self.send_to_clients(frame)

    async def receive_websocket_messages(self):
        while True:
            for client in self.clients:
                message = await client.recv()
                print(message)

    async def sock_handler(self, reader, writer):
        request = None
        while request != 'quit':
            #request = (await reader.read(255)).decode('utf8')
            response = str(eval(request)) + '\n'
            writer.write(response.encode('utf8'))
            await writer.drain()
        writer.close()

    async def websock_handler(self, websocket: WebSocketServerProtocol, path):
        await self.register(websocket)

        try:
            #while True:
                #message = await websocket.recv()
                #data = json.loads(message)
                #if data['action'] == 'start_streaming':
                    # Run the video streaming in a separate thread to prevent blocking
            #thr = Thread(target=lambda: asyncio.run(self.stream_video()))
            #thr.start()

            await asyncio.gather(self.stream_video(), self.receive_websocket_messages())
            #asyncio.create_task(self.receive_websocket_messages())

                #elif data['action'] == 'stop_streaming':
                    #break  # Implement stopping logic
                #else:
                    #print(f"Received command: {data['command']}")  # Implement command handling logic
        except websockets.exceptions.ConnectionClosed:
            print('Client disconnected')


if __name__ == "__main__":
    server = WebSocketServer()
    server.start()
