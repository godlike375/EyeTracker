from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLabel, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QGroupBox,
)
from PySide6.QtCore import Qt

from new_settings import AppSettings, BoundLineEdit, BoundCheckBox
from view.i18n import tr


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, fields: list = None, tooltips: dict = None,
                 parent=None, sections: list = None):
        super().__init__(parent)
        self.setWindowTitle(tr('file.settings').replace('&', ''))

        tooltips = tooltips or {}
        self.widgets = {}

        if sections is None:
            sections = [('', fields or [])]

        root = QVBoxLayout()
        columns = QHBoxLayout()
        columns.setAlignment(Qt.AlignTop)

        for title, section_fields in sections:
            group = QGroupBox(title) if title else QGroupBox()
            form = QFormLayout()
            for name, label in section_fields:
                obs = settings.get_setting(name)
                if not obs:
                    form.addRow(QLabel(label), QLabel("-"))
                    continue
                widget = BoundCheckBox(obs) if obs.type is bool else BoundLineEdit(obs)
                tip = tooltips.get(name)
                if tip:
                    widget.setToolTip(tip)
                label_widget = QLabel(label)
                if tip:
                    label_widget.setToolTip(tip)
                form.addRow(label_widget, widget)
                self.widgets[name] = widget
            group.setLayout(form)
            columns.addWidget(group)

        root.addLayout(columns)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons, alignment=Qt.AlignRight)

        self.setLayout(root)
