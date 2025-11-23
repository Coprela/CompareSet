"""Developer tools dialog for configuring CompareSet dev mode and layout editor."""
from __future__ import annotations

from typing import Dict, List

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QCheckBox,
    QVBoxLayout,
)

import compareset_env as csenv


class DeveloperToolsDialog(QDialog):
    """Modal dialog exposing developer simulation toggles."""

    settings_applied = Signal()
    layout_mode_toggled = Signal(bool)
    save_layout_requested = Signal()
    reset_layout_requested = Signal()

    def __init__(
        self,
        parent=None,
        settings: Dict | None = None,
        *,
        layout_mode_active: bool = False,
        developer_enabled: bool = False,
    ):
        super().__init__(parent)
        self.settings = settings or csenv.get_dev_settings()
        self.layout_mode_active = layout_mode_active
        self.developer_enabled = developer_enabled
        self.setWindowTitle("Developer Tools")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.dev_mode_checkbox = QCheckBox("Enable developer mode")
        self.dev_mode_checkbox.setChecked(bool(self.settings.get("dev_mode", False)))
        form.addRow(self.dev_mode_checkbox)

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
        self.theme_combo.addItem("Auto", None)
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.addItem("Dark", "dark")
        self._set_combo_value(self.theme_combo, self.settings.get("override_theme"))
        form.addRow("Theme", self.theme_combo)

        self.language_combo = QComboBox()
        self.language_combo.addItem("Auto", None)
        self.language_combo.addItem("Português (pt-BR)", "pt-BR")
        self.language_combo.addItem("English (en-US)", "en-US")
        self._set_combo_value(self.language_combo, self.settings.get("override_language"))
        form.addRow("Language", self.language_combo)

        self.super_admins_edit = QLineEdit(
            ", ".join(self._string_list(self.settings.get("super_admins", [])))
        )
        form.addRow(QLabel("Super admins (comma separated)"), self.super_admins_edit)

        self.local_testers_edit = QLineEdit(
            ", ".join(self._string_list(self.settings.get("local_storage_testers", [])))
        )
        form.addRow(QLabel("Local storage testers"), self.local_testers_edit)

        layout.addLayout(form)

        layout_controls = QHBoxLayout()
        self.layout_toggle_btn = QPushButton()
        self.layout_toggle_btn.setCheckable(True)
        self.layout_toggle_btn.setChecked(self.layout_mode_active)
        self._update_layout_button_label()
        self.layout_toggle_btn.clicked.connect(self._emit_layout_toggle)
        self.save_layout_btn = QPushButton("Save Layout")
        self.reset_layout_btn = QPushButton("Reset Layout")
        self.save_layout_btn.clicked.connect(self.save_layout_requested)
        self.reset_layout_btn.clicked.connect(self.reset_layout_requested)

        self.dev_mode_checkbox.toggled.connect(self._sync_layout_controls_enabled)

        for control in (self.layout_toggle_btn, self.save_layout_btn, self.reset_layout_btn):
            layout_controls.addWidget(control)
        self._sync_layout_controls_enabled()

        layout.addLayout(layout_controls)

        buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.apply_changes)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(max(index, 0))

    @staticmethod
    def _string_list(value) -> List[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        return []

    @staticmethod
    def _parse_list(text: str) -> list[str]:
        return [entry.strip() for entry in text.split(",") if entry.strip()]

    def _emit_layout_toggle(self) -> None:
        self.layout_mode_active = self.layout_toggle_btn.isChecked()
        self._update_layout_button_label()
        self.layout_mode_toggled.emit(self.layout_mode_active)

    def _update_layout_button_label(self) -> None:
        if self.layout_mode_active:
            self.layout_toggle_btn.setText("Exit Layout Mode")
        else:
            self.layout_toggle_btn.setText("Enter Layout Mode")

    def _sync_layout_controls_enabled(self) -> None:
        enabled = self.developer_enabled or self.dev_mode_checkbox.isChecked()
        for control in (self.layout_toggle_btn, self.save_layout_btn, self.reset_layout_btn):
            control.setEnabled(enabled)

    def apply_changes(self) -> None:
        updated = csenv.get_dev_settings()
        updated["dev_mode"] = self.dev_mode_checkbox.isChecked()
        updated["force_server_state"] = self.server_combo.currentData()
        updated["force_role"] = self.role_combo.currentData()
        updated["override_theme"] = self.theme_combo.currentData()
        updated["override_language"] = self.language_combo.currentData()
        updated["super_admins"] = self._parse_list(self.super_admins_edit.text())
        updated["local_storage_testers"] = self._parse_list(self.local_testers_edit.text())
        csenv.save_dev_settings(updated)
        csenv.reload_dev_settings()
        self.settings_applied.emit()
        QMessageBox.information(
            self,
            "Developer Tools",
            "Developer settings saved. Some changes may require restarting CompareSet.",
        )
        self.accept()
