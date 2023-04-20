from tkinter import messagebox

from common.logger import logger


def show_message(message: str, title: str = ''):
    logger.debug(message)
    messagebox.showinfo(title, message)

def show_warning(message: str, title: str = 'Предупреждение'):
    logger.warning(message)
    messagebox.showwarning(title, message)

def show_error(message: str, title: str = 'Ошибка'):
    logger.error(message)
    messagebox.showerror(title, message)


def show_fatal(e):
    show_message(title='Ошибка',
                 message=f'Фатальная ошибка.\n{e} \nРабота программы будет продолжена, но может стать нестабильной')
    logger.fatal(e)


def ask_confirmation(question):
    return messagebox.askyesno(title='Предупреждение', message=question)
