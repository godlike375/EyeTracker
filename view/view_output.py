from tkinter import messagebox
from functools import partial

from common.logger import logger


_view = None


def show_message(message: str, title: str = ''):
    logger.debug(message)
    _view._commands.queue_command(partial(messagebox.showinfo, title, message))


def show_warning(message: str, title: str = 'Предупреждение'):
    logger.warning(message)
    _view._commands.queue_command(partial(messagebox.showwarning, title, message))


def show_error(message: str, title: str = 'Ошибка'):
    logger.error(message)
    _view._commands.queue_command(partial(messagebox.showerror, title, message))


def show_fatal(e):
    show_message(title='Ошибка',
                 message=f'Фатальная ошибка.\n{e} \nРабота программы будет продолжена, но может стать нестабильной')
    logger.fatal(e)


def ask_confirmation(question):
    return messagebox.askyesno(title='Предупреждение', message=question)
