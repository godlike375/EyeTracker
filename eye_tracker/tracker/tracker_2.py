import cv2
import websocket
import base64
import numpy as np

class ObjectTrackerClient:
    def __init__(self):
        self.cap = None
        self.ws = None

    def track_object(self):
        self.cap = cv2.VideoCapture(0)

        while self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                break

            # Преобразование кадра в строку base64
            retval, frame_str = cv2.imencode('.jpg', frame)
            frame_base64 = base64.b64encode(frame_str)

            # Отправка кадра по WebSocket
            self.ws.send(frame_base64)

    def on_message(self, message):
        # Обработка полученного кадра
        frame = base64.b64decode(message)
        nparr = np.frombuffer(frame, dtype=np.uint8)
        decoded_frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Вывод кадра на экран
        cv2.imshow('Received Frame', decoded_frame)
        cv2.waitKey(1)

    def on_close(self):
        self.cap.release()
        cv2.destroyAllWindows()

    def receive_frames(self):
        self.ws = websocket.WebSocketApp("ws://localhost:8000",
                                         on_message=self.on_message,
                                         on_close=self.on_close)
        self.ws.run_forever()

    def start(self):
        self.receive_frames()

if __name__ == '__main__':
    client = ObjectTrackerClient()
    client.start()
