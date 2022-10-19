import cv2
from area_controller import AreaController
import argparse
pt_1 = (0, 0)
pt_2 = (0, 0)
mouse_down = False


def get_selected(cam):
    _, img = cam.read()
    # List containing top-left and bottom-right to crop the image.
    global pt_1, pt_2

    mouse_down = False

    def callback(event, x, y, flags, param):
        global pt_1, pt_2, mouse_down
        _, im_draw = cam.read()
        if event == cv2.EVENT_LBUTTONDOWN:
            mouse_down = True
            pt_1=(x, y)
        elif event == cv2.EVENT_LBUTTONUP and mouse_down == True:
            mouse_down = False
            pt_2 = (x, y)
            cv2.rectangle(im_draw, pt_1, pt_2, (255, 255, 255), 3)
            print("Object selected at [{}, {}]".format(pt_1, pt_2))
        elif event == cv2.EVENT_MOUSEMOVE and mouse_down == True:
            cv2.rectangle(im_draw, pt_1, (x, y), (255,255,255), 3)
        cv2.imshow("Image", im_draw)

    print("Press and release mouse around the object to be tracked. \n You can also select multiple objects.")
    cv2.setMouseCallback("Image", callback)

    print("Press key `p` to continue with the selected points.")
    print("Press key `d` to discard the last object selected.")
    print("Press key `q` to quit the program.")

    while True:
        # Draw the rectangular boxes on the image
        _, img2 = cam.read()

        window = (280, 120, 440, 270)
        cv2.circle(img2, AreaController.center(*window), 5, (255, 255, 255), 5)
        cv2.imshow("Image", img2)
        cv2.rectangle(img2, pt_1, pt_2, (255, 255, 255), 3)
        key = cv2.waitKey(16)
        if key == ord('p'):
            # Press key `s` to return the selected points
            corrected_point=check_point(pt_1, pt_2)
            return corrected_point
        elif key == ord('q'):
            # Press key `q` to quit the program
            print("Quitting without saving.")
            exit()
        elif key == ord('d'):
            # Press ket `d` to delete the last rectangular region
            if mouse_down == False and pt_1:
                print("Object deleted at  [{}, {}]".format(pt_1, pt_2))
                pt_1 = (0,0)
                pt_2 = (0,0)
                #im_disp = im.copy()
            else:
                print("No object to delete.")


def check_point(pt_1, pt_2):
    #to find min and max x coordinates
    minx, maxx = (pt_1[0], pt_2[0]) if pt_1[0]<pt_2[0] else (pt_2[0], pt_1[0])
    miny, maxy = (pt_1[1], pt_2[1]) if pt_1[1]<pt_2[1] else (pt_2[1], pt_1[1])
    out = (minx,miny,maxx,maxy)
    return out
