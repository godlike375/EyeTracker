limX = 10000
limY = 10000
lenX, lenY = 0,0
dX, dY = 0,0
cntr = (0,0)

def center(x,y,x2,y2):
    return int((x+x2)/2), int((y+y2)/2),

def setup(window):
    global startX, startY, lenX, lenY, dX, dY, cntr
    startX, startY, lenX, lenY = window[0], window[1],\
                                 abs(window[0]-window[2]), abs(window[1]-window[3])
    dX, dY = limX/lenX, limY/lenY
    cntr = center(window[0], window[1], window[2], window[3])



def map(x,y,x2,y2):
    cXY = center(x,y,x2,y2)
    return int(dX*(cXY[0]-cntr[0])), int(dY*(cXY[1]-cntr[1]))
    #центр бокса минус центр экрана умножить на коэффициент растяжения