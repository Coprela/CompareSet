from __future__ import annotations

import json
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
)


class DeveloperToolsDialog(QDialog):
    """Developer toolbox for layout editing, previews and diagnostics."""

    layout_mode_toggled = Signal(bool)
    save_layout_requested = Signal()
    reset_layout_requested = Signal()

    def __init__(self, window, *, layout_mode_active: bool = False) -> None:  # type: ignore[override]
        super().__init__(window)
        self.window = window
        self.layout_mode_active = layout_mode_active
        self.setWindowTitle("Developer Tools")
        self.setMinimumSize(760, 520)
        self._build_ui()
        self._refresh_areas()
        self._refresh_config_dump()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._build_layout_tab(), "Layout")
        tabs.addTab(self._build_preview_tab(), "View as role")
        tabs.addTab(self._build_config_tab(), "Config / JSON")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _build_layout_tab(self) -> QGroupBox:
        box = QGroupBox("Layout editor")
        layout = QVBoxLayout(box)

        header = QHBoxLayout()
        self.area_combo = QComboBox()
        self.area_combo.currentIndexChanged.connect(self._refresh_components)
        header.addWidget(QLabel("Area:"))
        header.addWidget(self.area_combo, 1)

        self.toggle_layout_btn = QPushButton()
        self.toggle_layout_btn.setCheckable(True)
        self.toggle_layout_btn.setChecked(self.layout_mode_active)
        self.toggle_layout_btn.clicked.connect(self._emit_layout_toggle)
        self._update_layout_toggle_label()
        header.addWidget(self.toggle_layout_btn)

        self.save_layout_btn = QPushButton("Save layout")
        self.save_layout_btn.clicked.connect(self.save_layout_requested)
        header.addWidget(self.save_layout_btn)

        self.reset_layout_btn = QPushButton("Reset layout")
        self.reset_layout_btn.clicked.connect(self.reset_layout_requested)
        header.addWidget(self.reset_layout_btn)
        layout.addLayout(header)

        grid = QGridLayout()
        self.component_list = QListWidget()
        self.component_list.currentItemChanged.connect(self._load_component)
        grid.addWidget(QLabel("Components"), 0, 0)
        grid.addWidget(self.component_list, 1, 0, 4, 1)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.display_mode_combo = QComboBox()
        self.display_mode_combo.addItems(["Text", "Icon", "Text + Icon"])
        self.icon_edit = QLineEdit()
        self.action_combo = QComboBox()
        for label, key in self.window.get_registered_actions().items():
            self.action_combo.addItem(label, key)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(0, 500)
        self.width_spin.setSpecialValueText("Default")
        self.height_spin = QSpinBox()
        self.height_spin.setRange(0, 200)
        self.height_spin.setSpecialValueText("Default")

        form.addRow("Label", self.name_edit)
        form.addRow("Display", self.display_mode_combo)
        form.addRow("Icon path", self.icon_edit)
        form.addRow("Action", self.action_combo)
        form.addRow("Min width", self.width_spin)
        form.addRow("Min height", self.height_spin)
        grid.addLayout(form, 1, 1, 3, 1)

        buttons = QHBoxLayout()
        self.add_button_btn = QPushButton("Add button")
        self.add_button_btn.clicked.connect(self._add_button)
        self.save_button_btn = QPushButton("Apply changes")
        self.save_button_btn.clicked.connect(self._apply_changes)
        self.move_up_btn = QPushButton("Move up")
        self.move_up_btn.clicked.connect(lambda: self._move_selected(-1))
        self.move_down_btn = QPushButton("Move down")
        self.move_down_btn.clicked.connect(lambda: self._move_selected(1))
        for btn in (self.add_button_btn, self.save_button_btn, self.move_up_btn, self.move_down_btn):
            buttons.addWidget(btn)
        grid.addLayout(buttons, 4, 1)

        layout.addLayout(grid)
        return box

    def _build_preview_tab(self) -> QGroupBox:
        box = QGroupBox("Preview permissions")
        layout = QFormLayout(box)
        self.role_combo = QComboBox()
        self.role_combo.addItem("Viewer / Read only", "viewer")
        self.role_combo.addItem("User", "user")
        self.role_combo.addItem("Admin", "admin")
        layout.addRow("View as", self.role_combo)

        preview_btn = QPushButton("Open preview")
        preview_btn.clicked.connect(self._open_preview)
        layout.addRow(preview_btn)
        return box

    def _build_config_tab(self) -> QGroupBox:
        box = QGroupBox("Layout snapshot")
        layout = QVBoxLayout(box)
        self.config_view = QTextEdit()
        self.config_view.setReadOnly(True)
        layout.addWidget(self.config_view)
        refresh_btn = QPushButton("Refresh data")
        refresh_btn.clicked.connect(self._refresh_config_dump)
        layout.addWidget(refresh_btn)
        return box

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------
    def _update_layout_toggle_label(self) -> None:
        self.toggle_layout_btn.setText("Exit layout mode" if self.layout_mode_active else "Enter layout mode")

    def _emit_layout_toggle(self) -> None:
        self.layout_mode_active = self.toggle_layout_btn.isChecked()
        self._update_layout_toggle_label()
        self.layout_mode_toggled.emit(self.layout_mode_active)

    def _refresh_areas(self) -> None:
        self.area_combo.blockSignals(True)
        self.area_combo.clear()
        for area in self.window.get_layout_areas():
            self.area_combo.addItem(area.get("label", area["key"]), area["key"])
        self.area_combo.blockSignals(False)
        if self.area_combo.count():
            self.area_combo.setCurrentIndex(0)
            self._refresh_components()

    def _refresh_components(self) -> None:
        area_key = self.area_combo.currentData()
        components = self.window.get_area_components(area_key)
        self.component_list.blockSignals(True)
        self.component_list.clear()
        for component in components:
            item = QListWidgetItem(component.get("display_name") or component.get("text") or component["id"])
            item.setData(256, component)
            self.component_list.addItem(item)
        self.component_list.blockSignals(False)
        if self.component_list.count():
            self.component_list.setCurrentRow(0)
        else:
            self._load_component(None)

    def _load_component(self, current: Optional[QListWidgetItem]) -> None:
        data = current.data(256) if current else None
        self._selected_component = data
        if not data:
            self.name_edit.clear()
            self.icon_edit.clear()
            self.width_spin.setValue(0)
            self.height_spin.setValue(0)
            self.action_combo.setCurrentIndex(0)
            return
        self.name_edit.setText(data.get("text") or data.get("display_name") or "")
        icon_value = data.get("icon", "")
        self.icon_edit.setText(str(icon_value or ""))
        self.width_spin.setValue(int(data.get("min_width", 0) or 0))
        self.height_spin.setValue(int(data.get("min_height", 0) or 0))
        display_mode = data.get("display_mode", "text")
        mode_map = {"text": 0, "icon": 1, "text_icon": 2}
        self.display_mode_combo.setCurrentIndex(mode_map.get(display_mode, 0))
        action = data.get("action", {}).get("type", "none")
        idx = self.action_combo.findData(action)
        self.action_combo.setCurrentIndex(max(idx, 0))

    def _add_button(self) -> None:
        area_key = self.area_combo.currentData()
        new_id = self.window.add_developer_button(area_key)
        if new_id:
            self._refresh_components()
            for idx in range(self.component_list.count()):
                item = self.component_list.item(idx)
                data = item.data(256) or {}
                if data.get("id") == new_id:
                    self.component_list.setCurrentRow(idx)
                    break
        else:
            QMessageBox.warning(self, "Layout", "Unable to create button for the selected area.")

    def _apply_changes(self) -> None:
        if not self._selected_component:
            return
        button_id = self._selected_component.get("id")
        if not button_id:
            return
        mode_idx = self.display_mode_combo.currentIndex()
        mode = "text" if mode_idx == 0 else "icon" if mode_idx == 1 else "text_icon"
        action_key = self.action_combo.currentData()
        updates = {
            "text": self.name_edit.text().strip() or "Novo botão",
            "icon": self.icon_edit.text().strip(),
            "display_mode": mode,
            "min_width": self.width_spin.value() or None,
            "min_height": self.height_spin.value() or None,
            "action": {"type": action_key} if action_key != "none" else {},
        }
        self.window.update_developer_button(button_id, updates)
        self._refresh_components()
        self._refresh_config_dump()

    def _move_selected(self, delta: int) -> None:
        current = self.component_list.currentItem()
        data = current.data(256) if current else None
        if not data:
            return
        if self.window.move_developer_button(data.get("id"), delta):
            self._refresh_components()

    def _open_preview(self) -> None:
        role = self.role_combo.currentData()
        self.window.open_role_preview(str(role))

    def _refresh_config_dump(self) -> None:
        snapshot = self.window.export_layout_snapshot()
        self.config_view.setPlainText(json.dumps(snapshot, indent=2, ensure_ascii=False))

