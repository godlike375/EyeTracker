from tkinter import Label, Tk, Frame

from PIL import ImageTk

from utils import FrameStorage

class MainForm:
    def __init__(self, tk: Tk, frame_storage: FrameStorage):
        self.window = tk
        # TODO: возможно растягивать картинку по размеру окна функцию сделать
        imageFrame = Frame(self.window, width=900, height=900)
        imageFrame.grid(row=0, column=1)
        self.video = Label(imageFrame, text="Video")
        self.frame_storage = frame_storage

    def setup(self):
        self.window.title("Text AI")
        self.window.geometry('700x700')
        self.window.configure(background="grey")
        self.video.grid(row=0, column=0)
        self.window.after(16, self.show_frame)
        return self

    def show_frame(self):
        frame = self.frame_storage.get_image()
        imgtk = ImageTk.PhotoImage(image=frame)
        self.video.configure(image=imgtk)
        self.window.after(16, self.show_frame)
