import sys
import os
from pathlib import Path
from functools import partial
from tkinter import Tk, END, colorchooser

from common.coordinates import Point
from common.settings import settings, private_settings, AREA, SelectedArea
from model.selector import LEFT_CLICK, LEFT_DOWN, LEFT_UP
from view import view_output
from view.drawing import Processor

MOUSE_EVENTS = ('<Button-1>', '<B1-Motion>', '<ButtonRelease-1>')
COLOR_RGB_INDEX = 0
G_INDEX = 1
R_INDEX = 0
B_INDEX = 2
PARAMETERS_APPLIED_AFTER_RESTART = 'Большинство параметров будут применены после перезапуска программы. ' \
                                   'Желаете перезапустить программу сейчас?'


class ViewModel:
    def __init__(self, root: Tk):
        self._root = root
        self._model = None
        self._view = None

    def set_model(self, model):
        self._model = model

    def set_view(self, view):
        self._view = view

    def on_image_ready(self, image):
        self._view.set_current_image(image)

    def calibrate_laser(self):
        self._model.calibrate_laser()

    def center_laser(self):
        self._model.center_laser()

    def move_laser(self, x, y):
        self._model.move_laser(x, y)

    def left_button_click(self, selector, event):
        selector.left_button_click(Point(event.x, event.y))

    def left_button_down_moved(self, selector, event):
        selector.left_button_down_moved(Point(event.x, event.y))

    def left_button_up(self, selector, event):
        selector.left_button_up(Point(event.x, event.y))

    def new_selection(self, name, retry_select_object_in_calibrating=False, additional_callback=None):
        # TODO: кроме name параметры нужны только чтобы передать их в new_selection модели
        #  то есть, эта функция используется и моделью и представлением, что выглядит странно, если подумать...
        selector = self._model.new_selection(name, retry_select_object_in_calibrating, additional_callback)

        if selector is None:
            return

        binded_left_click = (LEFT_CLICK, partial(self.left_button_click, selector))
        binded_left_down_moved = (LEFT_DOWN, partial(self.left_button_down_moved, selector))
        binded_left_up = (LEFT_UP, partial(self.left_button_up, selector))
        event_callbacks = dict([binded_left_click, binded_left_down_moved, binded_left_up])
        bindings = {}
        for event, callback, abstract_name in zip(MOUSE_EVENTS, event_callbacks.values(), event_callbacks.keys()):
            bindings[abstract_name] = partial(self._root.bind, event, callback)

        unbind_left_click = (LEFT_CLICK, partial(self._root.unbind, MOUSE_EVENTS[0]))
        unbind_left_down_moved = (LEFT_DOWN, partial(self._root.unbind, MOUSE_EVENTS[1]))
        unbind_left_up = (LEFT_UP, partial(self._root.unbind, MOUSE_EVENTS[2]))
        unbindings = (unbind_left_click, unbind_left_down_moved, unbind_left_up)

        selector.bind_events(bindings, unbindings)
        self._model.selecting.start_drawing(selector, name)

    def calibrate_noise_threshold(self):
        self._model.calibrate_noise_threshold(self._view.window_width, self._view.window_height)

    def calibrate_coordinate_system(self):
        self._model.calibrate_coordinate_system(self._view.window_width, self._view.window_height)

    def selector_is_selected(self, name):
        return self._model.selecting.selector_is_selected(name)

    def cancel_active_process(self):
        self._model.cancel_active_process()

    def progress_bar_set_visibility(self, visible):
        self._view._commands.queue_command(partial(self._view.progress_bar_set_visibility, visible))

    def set_progress(self, val):
        self._view._commands.queue_command(partial(self._view.set_progress, val))

    def get_progress(self):
        return self._view.get_progress()

    def set_tip(self, tip):
        self._view._commands.queue_command(partial(self._view.set_tip, f'Подсказка: {tip}'))

    def save_settings(self, params):
        errored = False
        for name, text_edit in params.items():
            text_param = text_edit.get(0.0, END)[:-1]
            try:
                number_param = float(text_param) if '.' in text_param else int(text_param)
            except ValueError:
                errored = True
                view_output.show_error(f'Некорректное значение параметра {name}:'
                                         f' ожидалось число, введено "{text_param}". Параметр не применён.')
            else:
                errored = not settings.__setattr__(name, number_param) or errored
        if errored:
            self._view.focus_on_settings_window()
            return
        settings.save()
        confirm = view_output.ask_confirmation(PARAMETERS_APPLIED_AFTER_RESTART)
        if confirm:
            self._model.stop_thread()
            private_settings.save()
            self.save_area()
            # TODO: останавливать работу программы нужно где-то в другом месте
            os.execv(str(Path.cwd() / sys.argv[0]), [sys.argv[0]])
            sys.exit()
        else:
            self._view.destroy_settings_window()

    def rotate_image(self, degree):
        self._model.rotate_image(degree)

    def flip_image(self, side):
        self._model.flip_image(side)

    def setup_window_geometry(self, reverse):
        self._view._commands.queue_command(partial(self._view.setup_window_geometry, reverse))

    def pick_color(self):
        color = colorchooser.askcolor()[COLOR_RGB_INDEX]
        if color is not None:
            private_settings.PAINT_COLOR_R = color[R_INDEX]
            private_settings.PAINT_COLOR_G = color[G_INDEX]
            private_settings.PAINT_COLOR_B = color[B_INDEX]
            Processor.load_color()

    def reset_settings(self):
        confirm = view_output.ask_confirmation('Вы точно желаете сбросить все настройки до значений по-умолчанию?')
        if not confirm:
            self._view.focus_on_settings_window()
            return
        settings.reset()
        private_settings.reset()
        confirm = view_output.ask_confirmation(PARAMETERS_APPLIED_AFTER_RESTART)
        if confirm:
            self._model.stop_thread()
            settings.save()
            private_settings.save()
            self.save_area()
            # TODO: останавливать работу программы нужно где-то в другом месте
            os.execv(str(Path.cwd() / sys.argv[0]), [sys.argv[0]])
            sys.exit()
        else:
            self._view.destroy_settings_window()

    def save_area(self):
        area_is_selected = self._model.selecting.selector_is_selected(AREA)
        if area_is_selected:
            if self._model.threshold_calibrator.in_progress and self._model.previous_area:
                self._model.save(self._model.previous_area.points)
            else:
                area_selector = self._model.selecting.get_selector(AREA)
                SelectedArea.save(area_selector.points)
