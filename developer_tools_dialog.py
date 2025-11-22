"""Developer tools dialog for configuring CompareSet dev mode."""
from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QVBoxLayout,
)

import compareset_env as csenv


class DeveloperToolsDialog(QDialog):
    """Modal dialog exposing developer simulation toggles."""

    settings_applied = Signal()

    def __init__(self, parent=None, settings: Dict | None = None):
        super().__init__(parent)
        self.settings = settings or csenv.get_dev_settings()
        self.setWindowTitle("Developer Tools")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.server_combo = QComboBox()
        self.server_combo.addItem("Auto", "auto")
        self.server_combo.addItem("Online", "online")
        self.server_combo.addItem("Offline", "offline")
        self._set_combo_value(self.server_combo, self.settings.get("force_server_state", "auto"))
        form.addRow("Server State", self.server_combo)

        self.role_combo = QComboBox()
        self.role_combo.addItem("None", "none")
        self.role_combo.addItem("Viewer", "viewer")
        self.role_combo.addItem("User", "user")
        self.role_combo.addItem("Admin", "admin")
        self._set_combo_value(self.role_combo, self.settings.get("force_role", "none"))
        form.addRow("User Role Override", self.role_combo)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Auto", "auto")
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.addItem("Dark", "dark")
        self._set_combo_value(self.theme_combo, self.settings.get("force_theme", "auto"))
        form.addRow("Theme", self.theme_combo)

        self.language_combo = QComboBox()
        self.language_combo.addItem("Auto", "auto")
        self.language_combo.addItem("Português (pt-BR)", "pt-BR")
        self.language_combo.addItem("English (en-US)", "en-US")
        self._set_combo_value(self.language_combo, self.settings.get("force_language", "auto"))
        form.addRow("Language", self.language_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.apply_changes)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(max(index, 0))

    def apply_changes(self) -> None:
        updated = csenv.get_dev_settings()
        updated["force_server_state"] = self.server_combo.currentData()
        updated["force_role"] = self.role_combo.currentData()
        updated["force_theme"] = self.theme_combo.currentData()
        updated["force_language"] = self.language_combo.currentData()
        csenv.save_dev_settings(updated)
        self.settings_applied.emit()
        self.accept()
