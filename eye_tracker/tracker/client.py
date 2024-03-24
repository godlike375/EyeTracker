import cv2
import socket
import pickle
import struct
import time

# Создаем сокет
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect(('127.0.0.1', 8000))

data = b""
payload_size = struct.calcsize("<L")


class FPSCounter:
    def __init__(self):
        self.start_time = time.time()
        self.frames = 0

    def calculate(self):
        current_time = time.time()
        elapsed_time = current_time - self.start_time

        if elapsed_time >= 1.0:
            fps = self.frames / elapsed_time
            self.frames = 0
            self.start_time = current_time
            return fps
        else:
            return 0

    def able_to_calculate(self):
        current_time = time.time()
        elapsed_time = current_time - self.start_time

        if elapsed_time >= 1.0:
            return True
        else:
            return False

fps_cnt = FPSCounter()

while True:
    while len(data) < payload_size:
        data += client_socket.recv(4096)

    packed_msg_size = data[:payload_size]
    data = data[payload_size:]
    msg_size = struct.unpack("<L", packed_msg_size)[0]

    while len(data) < msg_size:
        data += client_socket.recv(4096)

    frame_data = data[:msg_size]
    data = data[msg_size:]
    frame = pickle.loads(frame_data)

    #cv2.imshow('Video', frame)
    fps_cnt.frames += 1
    if fps_cnt.able_to_calculate():
        print(fps_cnt.calculate())
    #if cv2.waitKey(1) & 0xFF == ord('q'):
    #   break

cv2.destroyAllWindows()
client_socket.close()
