from functools import partial
from tkinter import messagebox

from model.common.logger import logger

_view = None


def show_message(message: str, title: str = ''):
    logger.debug(message)
    if _view is not None:
        _view.queue_command(partial(messagebox.showinfo, title, message))
    else:
        messagebox.showinfo(title, message)


def show_warning(message: str, title: str = 'Предупреждение'):
    logger.warning(message)
    if _view is not None:
        _view.queue_command(partial(messagebox.showwarning, title, message))
    else:
        messagebox.showwarning(title, message)


def show_error(message: str, title: str = 'Ошибка'):
    logger.error(message)
    if _view is not None:
        _view.queue_command(partial(messagebox.showerror, title, message))
    else:
        messagebox.showerror(title, message)


def show_fatal(e):
    show_error(title='Ошибка',
               message=f'Фатальная ошибка.\n{e}')
    logger.fatal(e)


def ask_confirmation(question):
    return messagebox.askyesno(title='Предупреждение', message=question)
