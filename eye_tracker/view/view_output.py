from functools import partial
from tkinter import messagebox, Tk

from eye_tracker.common.logger import logger

_view = None
DEFAULT_TIMEOUT_MS = 8500


def create_temp_messagebox(title, message, timeout, show_function):
    root = Tk()
    root.withdraw()
    root._planned_task_id = None
    _view._visible_messageboxes.append(root)

    def correctly_destroy_window():
        if not root in _view._visible_messageboxes:
            return
        root.after_cancel(root._planned_task_id)
        root.destroy()
        _view._visible_messageboxes.remove(root)

    root.protocol("WM_DELETE_WINDOW", correctly_destroy_window)

    root._planned_task_id = root.after(timeout, correctly_destroy_window)
    show_function(title, message, master=root)


def show_message(message: str, title: str = '', timeout=DEFAULT_TIMEOUT_MS):
    logger.debug(message)
    _view.queue_command(partial(create_temp_messagebox, title, message, timeout, messagebox.showinfo))


def show_warning(message: str, title: str = 'Предупреждение', timeout=DEFAULT_TIMEOUT_MS):
    logger.warning(message)
    _view.queue_command(partial(create_temp_messagebox, title, message, timeout, messagebox.showwarning))


def show_error(message: str, title: str = 'Ошибка', timeout=DEFAULT_TIMEOUT_MS):
    logger.error(message)
    _view.queue_command(partial(create_temp_messagebox, title, message, timeout, messagebox.showerror))


def show_fatal(e):
    show_error(title='Ошибка',
               message=f'Фатальная ошибка.\n{e}')
    logger.fatal(e)


def ask_confirmation(question):
    return messagebox.askyesno(title='Предупреждение', message=question)
