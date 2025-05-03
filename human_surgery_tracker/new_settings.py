import sys
import json
from typing import Any, Callable, Type, List, Dict, Generic, TypeVar, Tuple, Optional
from PyQt6.QtWidgets import QLineEdit, QWidget, QDialog, QFormLayout, QLabel, QApplication, QVBoxLayout, QPushButton, QDialogButtonBox, QCheckBox
from PyQt6.QtCore import Qt, QLocale
from PyQt6.QtGui import QPalette

T = TypeVar('T')

class ObservableValue(Generic[T]):
    def __init__(self, initial_value: T | None = None, min_val: T | None = None, max_val: T | None = None):
        self.value: T | None = initial_value
        self.type: Type | None = type(initial_value) if initial_value is not None else None
        self.callbacks: List[Callable[[T | None], None]] = []
        self.min: T | None = min_val
        self.max: T | None = max_val

    def register_callback(self, callback: Callable[[T | None], None]):
        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def set_value(self, new_value: T | None):
        old_value = self.value
        if self.type in (float, int) or isinstance(old_value, (float, int)):
            try:
                if abs(float(old_value or 0) - float(new_value or 0)) < 1e-9:
                    return
            except (TypeError, ValueError):
                if old_value == new_value:
                    return
        elif old_value == new_value:
            return
        self.value = new_value
        for cb in self.callbacks:
            try:
                cb(self.value)
            except Exception:
                pass

class AppSettings:
    def __init__(self, initial_data: Dict[str, Any] = None):
        self._settings: Dict[str, ObservableValue] = {}
        if initial_data:
            for key, value_info in initial_data.items():
                if isinstance(value_info, dict):
                    value = value_info.get("value")
                    min_val = value_info.get("min")
                    max_val = value_info.get("max")
                else:
                    value = value_info
                    min_val = None
                    max_val = None
                typ = type(value) if value is not None else None
                self._settings[key] = ObservableValue(value, min_val, max_val)

    def get_setting(self, field_name: str) -> Optional[ObservableValue]:
        return self._settings.get(field_name)

    def __getattr__(self, name: str) -> Any:
        if name in self._settings:
            return self._settings[name].value
        raise AttributeError(f"'AppSettings' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any):
        if name.startswith('_') or name in self.__dict__:
            super().__setattr__(name, value)
        elif name in self._settings:
            self._settings[name].set_value(value)
        else:
            raise AttributeError(f"'AppSettings' has no attribute '{name}'")

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for key, obs in self._settings.items():
            result[key] = obs.value
        return result

    def save(self, filename: str):
        data = {}
        for key, obs in self._settings.items():
            data[key] = {
                "value": obs.value,
                "min": obs.min,
                "max": obs.max,
                "type": str(obs.type),
            }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def load(self, filename: str):
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for key, loaded in data.items():
            if key in self._settings:
                obs = self._settings[key]
                obs.set_value(loaded["value"])
                obs.min = loaded.get("min")
                obs.max = loaded.get("max")


class BoundLineEdit(QLineEdit):
    def __init__(self, observable: ObservableValue, parent: QWidget = None):
        super().__init__(parent)
        self.observable = observable
        self.updating = False
        observable.register_callback(self.update_from_model)
        self.textEdited.connect(self.on_edit)
        self.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        self.update_from_model(observable.value)

    def update_from_model(self, value: Any):
        if self.updating:
            return
        self.updating = True
        try:
            text = str(value) if value is not None else ""
            if self.text() != text:
                self.setText(text)
            self.setStyleSheet("")
        finally:
            self.updating = False

    def on_edit(self, text: str):
        if self.updating:
            return
        try:
            t = text.strip()
            if self.observable.type is int and t:
                val = int(t)
                if self.observable.min is not None and val < self.observable.min:
                    val = self.observable.min
                if self.observable.max is not None and val > self.observable.max:
                    val = self.observable.max
            elif self.observable.type is float and t:
                val, ok = self.locale().toDouble(text)
                if not ok:
                    self.setStyleSheet("border: 1px solid red;")
                    return
                if self.observable.min is not None and val < self.observable.min:
                    val = self.observable.min
                if self.observable.max is not None and val > self.observable.max:
                    val = self.observable.max
            elif self.observable.type is bool:
                t = text.strip().lower()
                val = True if t in ('true', '1', 'yes') else False if t in ('false', '0', 'no') else None
            elif self.observable.type is str:
                val = text if text else None
            else:
                val = text
        except ValueError:
            self.setStyleSheet("border: 1px solid red;")
            return

        self.setStyleSheet("")
        self.observable.set_value(val)


class BoundCheckBox(QCheckBox):
    def __init__(self, observable: ObservableValue[bool | None], text: str = "", parent: QWidget = None):
        super().__init__(text, parent)
        self.observable = observable
        self.updating = False
        observable.register_callback(self.update_from_model)
        self.stateChanged.connect(self.on_change)
        self.update_from_model(observable.value)

    def update_from_model(self, value: bool | None):
        if self.updating:
            return
        self.updating = True
        try:
            state = Qt.CheckState.Checked if value is True else Qt.CheckState.Unchecked if value is False else Qt.CheckState.PartiallyChecked
            self.setCheckState(state)
        finally:
            self.updating = False

    def on_change(self, state: int):
        if self.updating:
            return
        val = {Qt.CheckState.Checked.value: True, Qt.CheckState.Unchecked.value: False, Qt.CheckState.PartiallyChecked.value: None}.get(state)
        self.observable.set_value(val)


class SettingsWindow(QDialog):
    def __init__(self, settings: AppSettings, fields: List[Tuple[str, str]], parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Настройки Приложения")
        layout = QFormLayout()
        self.widgets: Dict[str, QWidget] = {}

        for name, label in fields:
            obs = settings.get_setting(name)
            if not obs:
                layout.addRow(QLabel(label), QLabel("-"))
                continue
            widget = BoundCheckBox(obs) if obs.type is bool else BoundLineEdit(obs)
            layout.addRow(QLabel(label), widget)
            self.widgets[name] = widget

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app_settings = AppSettings({
        "username": "user_abc",
        "server_address": "192.168.1.100",
        "port": {"value": 8080, "min": 1024, "max": 65535},
        "log_filepath": "/tmp/my_app.log",
        "retry_count": {"value": 3, "min": 0, "max": 10},
        "timeout": {"value": 1.5, "min": 0.1, "max": 10.0},
        "is_enabled": True,
        "some_flag": None
    })

    # Для теста сохранения
    for field in app_settings.to_dict():
        obs = app_settings.get_setting(field)
        if obs:
            obs.register_callback(lambda v, f=field: print(f"{f}: {v}"))

    main_window = QWidget()
    main_window.setWindowTitle("Main Window")
    btn = QPushButton("Open Settings")
    layout = QVBoxLayout(main_window)
    layout.addWidget(btn)

    win = SettingsWindow(app_settings, [
        ("username", "User Name:"),
        ("server_address", "Server Address:"),
        ("port", "Port:"),
        ("log_filepath", "Log File Path:"),
        ("retry_count", "Retry Count:"),
        ("timeout", "Timeout (s):"),
        ("is_enabled", "Enabled:"),
        ("some_flag", "Some Flag:"),
    ])

    def save_test():
        app_settings.save("settings.json")
        print("Saved!")

    def load_test():
        app_settings.load("settings.json")
        print("Loaded!")

    btn.clicked.connect(win.exec)
    btn_save = QPushButton("Save Settings")
    btn_load = QPushButton("Load Settings")
    layout.addWidget(btn_save)
    layout.addWidget(btn_load)
    btn_save.clicked.connect(save_test)
    btn_load.clicked.connect(load_test)

    main_window.show()
    sys.exit(app.exec())