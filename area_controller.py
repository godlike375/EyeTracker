from utils import XY

class AreaController:

    def __init__(self, resolution_xy, min_xy, max_xy):
        # max resolution in abstract distance units
        self.resolution_xy = resolution_xy
        self.min_xy = min_xy
        self.max_xy = max_xy

    @staticmethod
    def calc_center(xy: XY, xy2: XY):
        return XY(int((xy.x+xy2.x)/2), int((xy.y+xy2.y)/2))

    def set_area(self, left_top, right_bottom):
        self.left_top = left_top
        self.right_bottom = right_bottom
        self.length_xy = XY(abs(left_top.x - right_bottom.x), abs(left_top.y - right_bottom.y))
        self.dpi_xy = XY(self.resolution_xy/self.length_xy.x, self.resolution_xy/self.length_xy.y)
        self.center = AreaController.calc_center(left_top, right_bottom)

    def rect_intersected_borders(self, left_top, right_bottom):
        if  left_top.x < self.left_top.x or \
            right_bottom.x > self.right_bottom.x or \
            left_top.y < self.left_top.y or \
            right_bottom.y > self.right_bottom.y:
                return True
        return False

    def point_intersected_borders(self, x, y):
        if  x < self.left_top.x or \
            x > self.right_bottom.x or \
            y < self.left_top.y or \
            y > self.right_bottom.y:
                return True
        return False
"""
    def map(x,y,x2,y2):
        cXY = Mapper.calc_center(x,y,x2,y2)
        return int(dX*(cXY[0]-cntr[0])), int(dY*(cXY[1]-cntr[1]))
        #центр бокса минус центр экрана умножить на коэффициент растяжения
"""