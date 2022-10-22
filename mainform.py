from tkinter import Label, Tk, Frame, Button, TOP, BOTTOM, LEFT, RIGHT

from PIL import ImageTk

from utils import FrameStorage, Settings
from dispatcher import EventDispatcher

class MainForm:
    def __init__(self, tk: Tk, frame_storage: FrameStorage, dispatcher: EventDispatcher):
        self.window = tk
        # TODO: возможно растягивать картинку по размеру окна функцию сделать

        imageFrame = Frame(self.window, width=600, height=800)
        imageFrame.pack(side=BOTTOM)
        self.buttonFrame = Frame(self.window, background='white')
        self.reset_area_rect = Button(self.buttonFrame, text='Выделение зоны', command=dispatcher.reset_area_selection)
        self.reset_object_rect = Button(self.buttonFrame, text='Выделение объекта', command=dispatcher.reset_object_selection)
        self.video = Label(imageFrame, text="Video")
        self.frame_storage = frame_storage

    def setup(self):
        self.window.title("Eye tracker")
        self.window.geometry(Settings.WINDOW_SIZE)
        self.window.configure(background='white')
        self.reset_area_rect.pack(side=LEFT, padx=16, pady=4)
        self.reset_object_rect.pack(side=RIGHT, padx=16, pady=4)
        self.video.pack(side=BOTTOM)
        self.buttonFrame.pack(side=TOP)
        self.window.after(Settings.CALL_EVERY, self.show_frame)
        return self

    def show_frame(self):
        frame = self.frame_storage.get_image()
        imgtk = ImageTk.PhotoImage(image=frame)
        self.video.configure(image=imgtk)
        self.window.after(Settings.CALL_EVERY, self.show_frame)
