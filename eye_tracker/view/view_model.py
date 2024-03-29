from functools import partial
from tkinter import Tk, END, colorchooser

from eye_tracker.common.program import exit_program
from eye_tracker.common.coordinates import Point
from eye_tracker.common.settings import settings, private_settings
from eye_tracker.model.selector import LEFT_CLICK, LEFT_DOWN, LEFT_UP
from eye_tracker.view import view_output
from eye_tracker.view.drawing import Processor

CALIBRATION_MENU_NAME = 'Откалибровать'
SELECTION_MENU_NAME = 'Выделить объект'
ROTATION_MENU_NAME = 'Повернуть'
FLIP_MENU_NAME = 'Отразить'
MANUAL_MENU_NAME = 'Ручное управление'
ABORT_MENU_NAME = 'Прервать'
SAME_RULES_CHANGEABLE = (CALIBRATION_MENU_NAME, ROTATION_MENU_NAME, FLIP_MENU_NAME, MANUAL_MENU_NAME)

MOUSE_EVENTS = ('<Button-1>', '<B1-Motion>', '<ButtonRelease-1>', '<KeyPress>')
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
        self._view._current_image = image

    def calibrate_laser(self):
        self._model.calibrate_laser()

    def center_laser(self):
        self._model.center_laser()

    def move_laser(self, x, y):
        self._model.move_laser(x, y)

    def _coordinates_on_video(self, event):
        full_width = self._model.current_frame.shape[1]
        full_height = self._model.current_frame.shape[0]
        x = event.x + (full_width - self._view._video_label.winfo_width()) // 2
        y = event.y + (full_height - self._view._video_label.winfo_height()) // 2
        x = x if x > 0 else 0
        x = x if x < full_width else full_width
        y = y if y > 0 else 0
        y = y if y < full_height else full_height

        if self._model.crop_zoomer.can_crop():
            zoomed_coordinates = self._model.crop_zoomer.to_zoom_area_coordinates(Point(x, y))
            x, y = zoomed_coordinates

        return x, y

    def left_button_click(self, selector, event):
        x, y = self._coordinates_on_video(event)
        selector.left_button_click(Point(x, y))

    def left_button_down_moved(self, selector, event):
        x, y = self._coordinates_on_video(event)
        selector.left_button_down_moved(Point(x, y))

    def left_button_up(self, selector, event):
        x, y = self._coordinates_on_video(event)
        selector.left_button_up(Point(x, y))

    def arrow_press(self, object_selector, event):
        if event.keysym == 'Up':
            object_selector.arrow_up()
        elif event.keysym == 'Down':
            object_selector.arrow_down()
        elif event.keysym == 'Left':
            object_selector.arrow_left()
        elif event.keysym == 'Right':
            object_selector.arrow_right()
        elif event.keysym == 'Return':  # (enter)
            object_selector.finish_selecting()
            self._model.state_control.change_state('enter pressed')

    def new_selection(self, name, reselect_while_calibrating=False, additional_callback=None, selector=None):
        # TODO: кроме name параметры нужны только чтобы передать их в new_selection модели
        #  то есть, эта функция используется и моделью и представлением, что выглядит странно, если подумать...

        selector = selector or \
                   self._model.selecting.try_create_selector(name, reselect_while_calibrating, additional_callback)
        if selector is None:
            return

        binded_left_click = (LEFT_CLICK, partial(self.left_button_click, selector))
        binded_left_down_moved = (LEFT_DOWN, partial(self.left_button_down_moved, selector))
        binded_left_up = (LEFT_UP, partial(self.left_button_up, selector))
        arrows = ('<KeyPress>', partial(self.arrow_press, selector))
        event_callbacks = dict([binded_left_click, binded_left_down_moved, binded_left_up, arrows])

        bindings = {}
        for event, callback, abstract_name in zip(MOUSE_EVENTS, event_callbacks.values(), event_callbacks.keys()):
            bindings[abstract_name] = partial(self._root.bind, event, callback)

        unbind_left_click = (LEFT_CLICK, partial(self._root.unbind, MOUSE_EVENTS[0]))
        unbind_left_down_moved = (LEFT_DOWN, partial(self._root.unbind, MOUSE_EVENTS[1]))
        unbind_left_up = (LEFT_UP, partial(self._root.unbind, MOUSE_EVENTS[2]))
        unbindings = (unbind_left_click, unbind_left_down_moved, unbind_left_up)

        selector.bind_events(bindings, unbindings)
        self._model.screen.add_selector(selector, name)

    def calibrate_noise_threshold(self):
        self._model.calibrate_noise_threshold()

    def calibrate_coordinate_system(self):
        self._model.calibrate_coordinate_system()

    def selector_is_selected(self, name):
        return self._model.selecting.selecting_is_done(name)

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
            exit_program(self._model, restart=True)
        else:
            self._view.destroy_settings_window()

    def rotate_image(self, degree):
        self._model.rotate_image(degree)

    def set_rotate_angle(self, angle):
        self._view._rotate_var.set(angle)

    def flip_image(self, side):
        self._model.flip_image(side)

    def set_flip_side(self, side):
        self._view._flip_var.set(side)

    def setup_window_geometry(self, reverse):
        self._view._commands.queue_command(partial(self._view.setup_window_geometry, reverse))

    def pick_color(self):
        color = colorchooser.askcolor()[COLOR_RGB_INDEX]
        if color is None:
            return

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
            exit_program(self._model, restart=True)
        else:
            self._view.destroy_settings_window()

    def set_menu_state(self, label, state):
        if label == 'all':
            for i in SAME_RULES_CHANGEABLE:
                self.execute_command(partial(self._view._menu.entryconfig, i, state=state))
            if state == 'disabled':
                self.set_menu_state(SELECTION_MENU_NAME, 'disabled')
                self.set_menu_state(ABORT_MENU_NAME, 'normal')
            elif state == 'normal':
                self.set_menu_state(ABORT_MENU_NAME, 'disabled')
            return

        self.execute_command(partial(self._view._menu.entryconfig, label, state=state))

    def execute_command(self, command):
        self._view.queue_command(command)
