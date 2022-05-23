class Mapper:
    limX = 10000
    limY = 10000
    lenX, lenY = 0,0
    dX, dY = 0,0
    cntr = (0,0)

    @staticmethod
    def center(x,y,x2,y2):
        return int((x+x2)/2), int((y+y2)/2),

    @staticmethod
    def setup(window):
        # TODO: эт чо, откуда переменные? Типа статических?
        global startX, startY, lenX, lenY, dX, dY, cntr
        startX, startY, lenX, lenY = window[0], window[1],\
                                     abs(window[0]-window[2]), abs(window[1]-window[3])
        dX, dY = Mapper.limX/lenX, Mapper.limY/lenY
        cntr = Mapper.center(window[0], window[1], window[2], window[3])

    @staticmethod
    def map(x,y,x2,y2):
        cXY = Mapper.center(x,y,x2,y2)
        return int(dX*(cXY[0]-cntr[0])), int(dY*(cXY[1]-cntr[1]))
        #центр бокса минус центр экрана умножить на коэффициент растяжения