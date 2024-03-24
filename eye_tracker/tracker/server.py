import cv2
import socket
import pickle
import struct

# Создаем сокет
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(('0.0.0.0', 8000))
server_socket.listen(5)

# Захватываем видеопоток с вебкамеры
camera = cv2.VideoCapture(0)

while True:
    client_socket, addr = server_socket.accept()
    if camera.isOpened():
        while True:
            ret, frame = camera.read()
            data = pickle.dumps(frame)
            client_socket.sendall(struct.pack("<L", len(data))+data)

    client_socket.close()

camera.release()
