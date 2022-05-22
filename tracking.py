import dlib
import cv2
import argparse as ap
import get_points
import process
import controller
import mapper
import time
#controller.init()



def catcherX(t):
    print('catcher')
    controller.moveX(t-5000)
    pass

def catcherY(t):
    controller.moveY(t-5000)
    pass

face_detector, eye_detector, detector = process.init_cv()
cv2.namedWindow('Image')
cv2.createTrackbar('x', 'Image', 0, 10000, catcherX)
cv2.createTrackbar('y', 'Image', 0, 10000, catcherY)
cv2.setTrackbarPos('x', 'Image', pos=5000)
cv2.setTrackbarPos('y', 'Image', pos=5000)





def main_loop(source=0, dispLoc=True):

    cam = cv2.VideoCapture(source)

    # If Camera Device is not opened, exit the program
    if not cam.isOpened():
        print("Video device or file couldn't be opened")
        exit()

    # Co-ordinates of objects to be tracked
    # will be stored in a list named `points`
    #window = get_points.run(cam)
    window = (280, 120, 440, 270)

    mapper.setup(window)

    point = get_points.run(cam)

    if not point:
        print("ERROR: No object to be tracked.")
        exit()
    retval, img = cam.read()
    cv2.namedWindow("Image", cv2.WINDOW_NORMAL)
    cv2.imshow("Image", img)

    tracker = dlib.correlation_tracker()
    # Provide the tracker the initial position of the object
    tracker.start_track(img, dlib.rectangle(*point))
    tracker.update(img)
    rect = tracker.get_position()
    pt1 = (int(rect.left()), int(rect.top()))
    lastX, lastY = pt1[1], pt1[0]

    while True:
        # Read frame from device or file
        retval, img = cam.read()
        if not retval:
            print("Cannot capture frame device | CODE TERMINATING :(")
            exit()
        tracker.update(img)
        rect = tracker.get_position()

        pt1 = (int(rect.left()), int(rect.top()))
        pt2 = (int(rect.right()), int(rect.bottom()))
        cv2.rectangle(img, pt1, pt2, (255, 255, 255), 3)
        centerXY = mapper.center(pt1[0], pt1[1], pt2[0], pt2[1])
        deltaX = abs(controller.X - centerXY[0])
        deltaY = abs(controller.Y - centerXY[1])

        if controller.canSend():
            if deltaX > 200 or deltaY > 200:
                coords = mapper.map(pt1[0], pt1[1], pt2[0], pt2[1])
                print(coords)
                controller.moveXY(coords[0], coords[1])
                controller.reset()
            #controller.moveX(coords[0])
            #controller.moveY(coords[1])
            '''
            dY, dX = pt1[0]-lastY, pt1[1]-lastX
            mY, mX = dY*controller.deltaStep, dX*controller.deltaStep
            mX = 0 if abs(mX) < 40 else mX
            mY = 0 if abs(mY) < 40 else mY
            lastX, lastY = pt1[1], pt1[0]
            '''



        #print("Object tracked at [{}, {}] \r".format(pt1, pt2))
        if dispLoc:
            loc = (int(rect.left()), int(rect.top() - 20))
            txt = "Object tracked at [{}, {}]".format(pt1, pt2)
            #cv2.putText(img, txt, loc, cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
        cv2.namedWindow("Image", cv2.WINDOW_NORMAL)
        cv2.imshow("Image", img)
        # Continue until the user presses ESC key
        if cv2.waitKey(16) == ord('q'):
            controller.reset()
            while not controller.canSend():
                pass
            controller.moveXY(0,0)
            controller.reset()
            while not controller.canSend(2.5):
                pass
            exit()

    # Relase the VideoCapture object
    cam.release()

main_loop(0, False)