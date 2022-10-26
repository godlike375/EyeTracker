from tkinter import Label, Tk, Frame, Button, TOP, BOTTOM, LEFT, RIGHT

from PIL import ImageTk

from management_core import EventDispatcher, FrameStorage
from model.settings import Settings

SECOND_LENGHT = 1000

class MainForm(Frame):
    def __init__(self, tk: Tk, frame_storage: FrameStorage, dispatcher: EventDispatcher):
        self.window = tk
        # TODO: возможно растягивать картинку по размеру окна функцию сделать
        self.image_alive_ref = None
        self.imageFrame = Frame(self.window, width=600, height=800)
        self.buttonFrame = Frame(self.window, background='white')
        self.select_area_rect = Button(self.buttonFrame, text='Выделение зоны',
                                       command=dispatcher.reset_area_selection)
        self.select_object_rect = Button(self.buttonFrame, text='Выделение объекта',
                                         command=dispatcher.reset_object_selection)
        self.calibrate_laser = Button(self.buttonFrame, text='Откалибровать лазер',
                                      command=dispatcher.calibrate_laser)
        self.center_laser = Button(self.buttonFrame, text='Завершить сеанс',
                                      command=dispatcher.center_laser)
        self.video = Label(self.imageFrame, text="Video")
        self.frame_storage = frame_storage

    def setup(self):
        self.window.title("Eye tracker")
        window_size = f'{Settings.WINDOW_HEIGHT}x{Settings.WINDOW_WIDTH}'
        self.window.geometry(window_size)
        self.window.configure(background='white')
        self.imageFrame.pack(side=BOTTOM)
        self.calibrate_laser.pack(side=LEFT, padx=16, pady=4)
        self.center_laser.pack(side=LEFT, padx=16, pady=4)
        self.select_area_rect.pack(side=LEFT, padx=16, pady=4)
        self.select_object_rect.pack(side=RIGHT, padx=16, pady=4)
        self.video.pack(side=BOTTOM)
        self.buttonFrame.pack(side=TOP)
        self.interval_ms = int(Settings.INTERVAL*SECOND_LENGHT)
        self.window.after(self.interval_ms, self.show_frame)
        return self

    def show_frame(self):
        frame = self.frame_storage.get_image()
        imgtk = ImageTk.PhotoImage(image=frame)
        #! если не сохранить ссылку на этот объект где-нибудь, то объект тут же удалится и не будет отображаться картинка
        self.image_alive_ref = imgtk
        self.video.configure(image=imgtk)
        self.window.after(self.interval_ms, self.show_frame)
