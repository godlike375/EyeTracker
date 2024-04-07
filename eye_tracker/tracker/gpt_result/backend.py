import asyncio
import cv2
import websockets
import socket
from threading import Thread


FRONTEND_PORT = 8000
TRACKER_PORT = 9000
BUFF_SIZE = 65536


class FrontendConnection:
    def __init__(self, websocket):
        self.websocket = websocket

    async def send_video(self, capture):
        while True:
            ret, frame = capture.read()
            if not ret:
                break
            _, encoded = cv2.imencode('.jpg', frame)
            await self.websocket.send(encoded.tobytes())


class TrackerConnection:
    def __init__(self, client_socket):
        self.client_socket = client_socket

    def receive_coordinates(self):
        while True:
            try:
                data = self.client_socket.recv(4096)
                if not data:
                    break
                # Обработать полученные координаты отслеживаемого объекта от Tracker
            except socket.error as e:
                break

    def send_video(self, capture):
        while True:
            ret, frame = capture.read()
            if not ret:
                break
            _, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
            self.client_socket.send(encoded.tobytes())


async def handle_frontend(websocket, path, tracker_connections):
    frontend = FrontendConnection(websocket)
    capture = cv2.VideoCapture(0)

    try:
        await frontend.send_video(capture)
    except websockets.exceptions.ConnectionClosedOK:
        pass


async def handle_commands(websocket, tracker_connections):
    async for message in websocket:
        # Обработать полученные команды от Frontend
        pass


def handle_tracker(tracker_socket):
    tracker = TrackerConnection(tracker_socket)
    capture = cv2.VideoCapture(0)
    capture.set(cv2.CAP_PROP_FPS, 60)
    tracker.send_video(capture)


async def accept_frontend_connections(server, tracker_connections):
    while True:
        websocket, _ = await server.accept()
        task = asyncio.create_task(handle_frontend(websocket, '', tracker_connections))
        await task


def accept_tracker_connections():
    while True:
        client_socket, _ = start_tracker.accept()
        thread = Thread(target=handle_tracker, args=(client_socket,))
        thread.start()


async def start_backend():
    server = await websockets.serve(handle_commands, 'localhost', FRONTEND_PORT)

    frontend_connections = set()
    trackers = set()

    async with server:
        await asyncio.gather(accept_frontend_connections(server, trackers), accept_tracker_connections())

start_tracker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
start_tracker.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,BUFF_SIZE)
start_tracker.bind(('localhost', TRACKER_PORT))
start_tracker.listen()

asyncio.run(start_backend())
