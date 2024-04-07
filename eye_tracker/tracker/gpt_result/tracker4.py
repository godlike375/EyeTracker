import websocket
import threading
import dlib
import cv2
import json

def on_message(ws, message):
    # обработка изображения и отправка координат обратно в Backend
    pass

def on_error(ws, error):
    print(error)

def on_close(ws):
    print("### closed ###")

def on_open(ws):
    def run(*args):
        # отправка изображений на обработку
        pass
    threading.Thread(target=run).start()

class Backend:
    def __init__(self):
        self.ws = websocket.WebSocketApp("ws://localhost:8000/",
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)
        threading.Thread(target=self.ws.run_forever).start()

    def send_tracking_data(self, data):
        # отправка данных об отслеживании
        self.ws.send(json.dumps(data))

if __name__ == "__main__":
    backend = Backend()