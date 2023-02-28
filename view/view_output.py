from tkinter import messagebox

from common.logger import logger


def show_message(message: str, title: str = ''):
    messagebox.showerror(title, message)


def show_warning(message: str):
    messagebox.showerror('Предупреждение', message)


def show_fatal(e):
    show_message(title='Ошибка',
                 message=f'Фатальная ошибка.\n{e} \nРабота программы будет продолжена, но может стать нестабильной')
    logger.fatal(e)
