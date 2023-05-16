from functools import partial
from tkinter import (
    Label, Frame,
    X, Toplevel,
    Text, Button, LEFT,
    messagebox, END, RIGHT,
)

from model.common.logger import logger
from model.common.settings import settings, get_repo_path


ZERO_LINE_AND_COLUMN = 0.0
MARGIN_FIELDS = 3
BUTTON_MARGIN = MARGIN_FIELDS * 10


class WindowSettings:
    def __init__(self, root, view_model):
        self._root = root
        self._view_model = view_model
        self._settings = None

    def open_settings(self):
        if self._settings is not None:
            self.focus_on_settings_window()
            return
        self._settings = Toplevel(self._root)
        self._settings.title('Настройки')
        try:
            self._settings.iconbitmap(str(get_repo_path(bundled=True) / "tracking.ico"))
        except Exception:
            logger.warning('tracking.ico not found')

        reset_settings_button = Button(self._settings, command=self._view_model.reset_settings,
                                       text='Сбросить настройки')
        reset_settings_button.pack(pady=MARGIN_FIELDS)

        params = {}
        for param in dir(settings):
            if param.isupper():
                frame = Frame(self._settings)
                frame.pack(fill=X)
                label = Label(frame, text=f'{param} =')
                label.pack(side=LEFT, pady=MARGIN_FIELDS, padx=MARGIN_FIELDS)

                text_param = str(getattr(settings, param))
                edit = Text(frame, width=len(text_param) + 1, height=1)
                params[param] = edit
                edit.pack(side=LEFT, pady=MARGIN_FIELDS, padx=MARGIN_FIELDS)
                edit.insert(ZERO_LINE_AND_COLUMN, text_param)
        pick_color_button = Button(self._settings, command=self._view_model.pick_color, text='Выбрать цвет отрисовки')
        pick_color_button.pack(pady=MARGIN_FIELDS)

        buttons_frame = Frame(self._settings)
        buttons_frame.pack(pady=MARGIN_FIELDS)
        save_settings = partial(self._view_model.save_settings, params)
        exit_settings = partial(self.exit_settings, params)
        self._settings.protocol("WM_DELETE_WINDOW", exit_settings)
        exit_settings_button = Button(buttons_frame, command=exit_settings, text='Закрыть')
        save_button = Button(buttons_frame, command=save_settings, text='Сохранить')
        save_button.pack(padx=BUTTON_MARGIN, side=RIGHT)
        exit_settings_button.pack(padx=BUTTON_MARGIN, side=LEFT)

    def exit_settings(self, params):
        global_settings = [getattr(settings, name) for name in dir(settings) if name.isupper()]
        current_settings = []
        for name, text_edit in params.items():
            text_param = text_edit.get(0.0, END)[:-1]
            try:
                number_param = float(text_param) if '.' in text_param else int(text_param)
            except ValueError:
                self.destroy_settings_window()
                return
            else:
                current_settings.append(number_param)
        if current_settings == global_settings:
            self.destroy_settings_window()
            return
        else:
            exit_confirm = messagebox.askyesno(title='Предупреждение',
                                               message='Имеются несохранённые параметры. '
                                                       'Хотите закрыть окно без сохранения?')
            self.focus_on_settings_window()
            if exit_confirm:
                self.destroy_settings_window()

    def destroy_settings_window(self):
        self._settings.destroy()
        self._settings = None

    def focus_on_settings_window(self):
        if self._settings:
            self._settings.focus_force()