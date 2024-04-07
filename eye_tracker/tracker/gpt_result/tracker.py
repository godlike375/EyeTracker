import socket
import cv2
import numpy

backend_host = 'localhost'
backend_port = 9000
BUFF_SIZE = 65536


def connect_to_backend():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
    s.connect((backend_host, backend_port))
    return s


def receive_image(conn):
    data = b''
    while True:
        packet = conn.recv(4096)
        print(packet)
        if not packet:
            print('no data')
            break
        data += packet
    return data


def track_object():
    conn = connect_to_backend()

    while True:
        image_data, _ = conn.recvfrom(BUFF_SIZE)
        image: numpy.ndarray = cv2.imdecode(numpy.frombuffer(image_data, dtype=numpy.uint8), cv2.IMREAD_COLOR)
        try:
            if not image is None and image.size > 0:
                cv2.imshow('Tracking', image)
                cv2.waitKey(1)
        except ValueError:
            print(image)

        # Отслеживание объекта и отправка координат на Backend


if __name__ == '__main__':
    track_object()
