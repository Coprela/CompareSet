"""No-code layout designer for CompareSet developer mode."""
from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)


class LayoutDesignerDialog(QDialog):
    """Visual editor that tweaks text and styling without touching Python code."""

    def __init__(self, window) -> None:  # type: ignore[override]
        super().__init__(window)
        self.window = window
        self.catalog = window.get_editable_widget_catalog()
        self.setWindowTitle("Layout Designer")
        self._build_ui()
        self._refresh_catalog()

        if self.widget_list.count():
            self.widget_list.setCurrentRow(0)
        self._lock_to_content()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        header_row = QHBoxLayout()
        header_row.addWidget(
            QLabel(
                "Arraste os painéis usando o modo Layout Editor. Aqui você pode alterar textos, "
                "cores e tamanhos sem programar. Selecione um elemento, edite e clique em Apply."
            )
        )
        self.add_button_btn = QPushButton("Add button…")
        self.add_button_btn.clicked.connect(self._add_dynamic_button)
        self.add_button_btn.setEnabled(False)
        self.add_button_btn.setVisible(False)
        header_row.addWidget(self.add_button_btn)
        layout.addLayout(header_row)

        self.widget_list = QListWidget()
        self.widget_list.currentItemChanged.connect(self._on_selection_changed)

        layout.addWidget(self.widget_list)

        form = QFormLayout()
        self.text_edit = QLineEdit()
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(0, 72)
        self.font_size_spin.setSpecialValueText("Padrão")
        self.font_size_spin.setValue(0)
        self.bold_checkbox = QCheckBox("Negrito")
        self.color_edit = QLineEdit()
        self.color_edit.setPlaceholderText("Ex.: #222222 ou red")
        self.background_edit = QLineEdit()
        self.background_edit.setPlaceholderText("Ex.: #f5f5f5")
        self.border_color_edit = QLineEdit()
        self.border_color_edit.setPlaceholderText("Cor da borda")
        self.border_width_spin = QSpinBox()
        self.border_width_spin.setRange(0, 12)
        self.border_width_spin.setSpecialValueText("Padrão")
        self.hover_text_edit = QLineEdit()
        self.hover_text_edit.setPlaceholderText("Cor do texto ao passar o mouse")
        self.hover_background_edit = QLineEdit()
        self.hover_background_edit.setPlaceholderText("Cor do fundo ao passar o mouse")
        self.icon_edit = QLineEdit()
        self.icon_edit.setPlaceholderText("Ícone ou imagem (caminho)")
        self.x_spin = QSpinBox()
        self.x_spin.setRange(-5000, 5000)
        self.y_spin = QSpinBox()
        self.y_spin.setRange(-5000, 5000)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(0, 5000)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(0, 5000)
        self.action_combo = QComboBox()
        self.action_combo.addItem("Sem ação extra", "none")
        self.action_combo.addItem("Abrir URL", "url")
        self.action_combo.addItem("Abrir arquivo local", "file")
        self.action_combo.addItem("Chamar método", "method")
        self.action_combo.addItem("Abrir diálogo", "dialog")
        self.action_target_edit = QLineEdit()
        self.action_target_edit.setPlaceholderText("URL, caminho do arquivo ou nome do método")

        form.addRow("Texto", self.text_edit)
        form.addRow("Tamanho da fonte", self.font_size_spin)
        form.addRow("", self.bold_checkbox)
        form.addRow("Cor do texto", self.color_edit)
        form.addRow("Fundo", self.background_edit)
        form.addRow("Borda (cor)", self.border_color_edit)
        form.addRow("Borda (largura)", self.border_width_spin)
        form.addRow("Hover (texto)", self.hover_text_edit)
        form.addRow("Hover (fundo)", self.hover_background_edit)
        form.addRow("Ícone/imagem", self.icon_edit)
        form.addRow("Posição X", self.x_spin)
        form.addRow("Posição Y", self.y_spin)
        form.addRow("Largura", self.width_spin)
        form.addRow("Altura", self.height_spin)
        form.addRow("Ação extra", self.action_combo)
        form.addRow("Destino da ação", self.action_target_edit)
        layout.addLayout(form)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Pré-visualização do estilo em CSS")
        layout.addWidget(self.preview)

        button_row = QHBoxLayout()
        self.apply_button = QPushButton("Apply")
        self.reset_button = QPushButton("Reset widget")
        self.close_button = QPushButton("Close")
        self.apply_button.clicked.connect(self._apply_changes)
        self.reset_button.clicked.connect(self._reset_widget)
        self.close_button.clicked.connect(self.accept)
        button_row.addWidget(self.apply_button)
        button_row.addWidget(self.reset_button)
        button_row.addStretch()
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)

    def _refresh_catalog(self, select_key: Optional[str] = None) -> None:
        current_key = select_key
        if current_key is None and self.widget_list.currentItem():
            current_key = self.widget_list.currentItem().data(Qt.UserRole)
        self.catalog = self.window.get_editable_widget_catalog()
        self.widget_list.blockSignals(True)
        self.widget_list.clear()
        for key, info in self.catalog.items():
            item = QListWidgetItem(str(info.get("display_name", key)))
            item.setData(Qt.UserRole, key)
            self.widget_list.addItem(item)
        self.widget_list.blockSignals(False)
        if self.widget_list.count():
            target_row = 0
            if current_key is not None:
                for idx in range(self.widget_list.count()):
                    item = self.widget_list.item(idx)
                    if item.data(Qt.UserRole) == current_key:
                        target_row = idx
                        break
            self.widget_list.setCurrentRow(target_row)
        self.add_button_btn.setEnabled(bool(self.window.get_dynamic_parents()))

    def _lock_to_content(self) -> None:
        self.adjustSize()
        size = self.sizeHint()
        if self.screen():
            available = self.screen().availableGeometry().size() - QSize(24, 24)
            if available.isValid():
                size = size.boundedTo(available)
        self.setFixedSize(size)

    def _on_selection_changed(self, current: Optional[QListWidgetItem]) -> None:
        key = current.data(Qt.UserRole) if current else None
        self._load_widget_state(key)

    def _load_widget_state(self, key: Optional[str]) -> None:
        info = self.catalog.get(key or "", {})
        state = self.window.get_widget_state(key or "")
        defaults = state.get("defaults", {})
        overrides = state.get("overrides", {})
        allow_text = bool(info.get("allow_text", True))
        allow_style = bool(info.get("allow_style", True))
        allow_icon = bool(info.get("allow_icon", False))
        allow_geometry = bool(info.get("allow_geometry", True))
        allow_action = bool(info.get("allow_action", False))

        current_text = overrides.get("text") or defaults.get("text") or ""
        self.text_edit.setText(current_text)
        self.text_edit.setEnabled(allow_text)
        self.font_size_spin.setEnabled(allow_style)
        self.bold_checkbox.setEnabled(allow_style)
        self.color_edit.setEnabled(allow_style)
        self.background_edit.setEnabled(allow_style)
        self.border_color_edit.setEnabled(allow_style)
        self.border_width_spin.setEnabled(allow_style)
        self.hover_text_edit.setEnabled(allow_style)
        self.hover_background_edit.setEnabled(allow_style)
        self.preview.setEnabled(allow_style)
        self.icon_edit.setEnabled(allow_icon)

        geom_source = overrides.get("geometry") or state.get("geometry") or {}
        widget = state.get("widget")
        rect = widget.geometry() if widget else None
        self.x_spin.setValue(int(geom_source.get("x", rect.x() if rect else 0)))
        self.y_spin.setValue(int(geom_source.get("y", rect.y() if rect else 0)))
        self.width_spin.setValue(int(geom_source.get("width", rect.width() if rect else 0)))
        self.height_spin.setValue(int(geom_source.get("height", rect.height() if rect else 0)))
        for spinner in (self.x_spin, self.y_spin, self.width_spin, self.height_spin):
            spinner.setEnabled(allow_geometry)

        style_source = overrides.get("style") or defaults.get("style") or ""
        parsed_style = self._parse_style(style_source)
        self.font_size_spin.setValue(parsed_style.get("font_size", 0))
        self.bold_checkbox.setChecked(parsed_style.get("bold", False))
        self.color_edit.setText(parsed_style.get("color", ""))
        self.background_edit.setText(parsed_style.get("background", ""))
        self.border_color_edit.setText(parsed_style.get("border_color", ""))
        self.border_width_spin.setValue(parsed_style.get("border_width", 0))
        self.hover_text_edit.setText(parsed_style.get("hover_text", ""))
        self.hover_background_edit.setText(parsed_style.get("hover_background", ""))
        self.icon_edit.setText(str(overrides.get("icon", "")) if allow_icon else "")

        action_data: Dict[str, Any] = {}
        if allow_action:
            if isinstance(overrides.get("action"), dict):
                action_data = overrides.get("action", {})
            elif isinstance(state.get("action"), dict):
                action_data = state.get("action", {})
        action_type = action_data.get("type", "none")
        idx = self.action_combo.findData(action_type)
        self.action_combo.setCurrentIndex(max(idx, 0))
        self.action_combo.setEnabled(allow_action)
        self.action_target_edit.setEnabled(allow_action)
        self.action_target_edit.setText(str(action_data.get("value") or action_data.get("target") or ""))

        self.preview.setPlainText(style_source.strip())

    def _parse_style(self, style: str) -> Dict[str, str | int | bool]:
        parsed: Dict[str, str | int | bool] = {}
        tokens = [segment.strip() for segment in style.replace("{", ";").replace("}", ";").split(";") if segment.strip()]
        for token in tokens:
            if token.startswith("color:") and "hover" not in token:
                parsed["color"] = token.split(":", 1)[1].strip()
            elif token.startswith("background-color:") and "hover" not in token:
                parsed["background"] = token.split(":", 1)[1].strip()
            elif token.startswith("font-size:"):
                try:
                    parsed["font_size"] = int(token.split(":", 1)[1].strip().replace("px", ""))
                except ValueError:
                    pass
            elif token.startswith("font-weight:"):
                try:
                    weight = int(token.split(":", 1)[1].strip())
                    parsed["bold"] = weight >= 600
                except ValueError:
                    pass
            elif token.startswith("border:"):
                parts = token.split()
                for part in parts:
                    if part.endswith("px"):
                        try:
                            parsed["border_width"] = int(part.replace("px", ""))
                        except ValueError:
                            pass
                    elif part != "border:" and part != "solid":
                        parsed["border_color"] = part
            elif token.startswith("hover-color:"):
                parsed["hover_text"] = token.split(":", 1)[1].strip()
            elif token.startswith("hover-background:"):
                parsed["hover_background"] = token.split(":", 1)[1].strip()
        return parsed

    def _build_style(self, defaults: Dict[str, Optional[str]]) -> Optional[str]:
        rules = []
        if self.color_edit.text().strip():
            rules.append(f"color: {self.color_edit.text().strip()};")
        if self.background_edit.text().strip():
            rules.append(f"background-color: {self.background_edit.text().strip()};")
        if self.font_size_spin.value() > 0:
            rules.append(f"font-size: {self.font_size_spin.value()}px;")
        if self.bold_checkbox.isChecked():
            rules.append("font-weight: 600;")
        if self.border_width_spin.value() > 0:
            border_color = self.border_color_edit.text().strip() or "#000"
            rules.append(f"border: {self.border_width_spin.value()}px solid {border_color};")
        hover_rules = []
        if self.hover_text_edit.text().strip():
            hover_rules.append(f"color: {self.hover_text_edit.text().strip()};")
        if self.hover_background_edit.text().strip():
            hover_rules.append(f"background-color: {self.hover_background_edit.text().strip()};")
        base_style = defaults.get("style") or ""
        if not rules and not hover_rules:
            return None
        style_parts = [base_style.strip()] if base_style.strip() else []
        if rules:
            style_parts.append(" ".join(rules))
        if hover_rules:
            style_parts.append(
                f"QPushButton:hover {{ {' '.join(hover_rules)} hover-color:{self.hover_text_edit.text().strip()}; hover-background:{self.hover_background_edit.text().strip()}; }}"
            )
        return "\n".join(style_parts).strip()

    def _apply_changes(self) -> None:
        current_item = self.widget_list.currentItem()
        key = current_item.data(Qt.UserRole) if current_item else None
        if key is None:
            return
        info = self.catalog.get(key, {})
        allow_text = bool(info.get("allow_text", True))
        allow_style = bool(info.get("allow_style", True))
        allow_icon = bool(info.get("allow_icon", False))
        allow_geometry = bool(info.get("allow_geometry", True))
        allow_action = bool(info.get("allow_action", False))
        defaults = self.window._widget_defaults.get(key, {})

        overrides: Dict[str, Any] = {}
        new_text = self.text_edit.text()
        if allow_text and new_text != defaults.get("text"):
            overrides["text"] = new_text

        style_override = self._build_style(defaults) if allow_style else None
        if allow_style and style_override:
            overrides["style"] = style_override

        if allow_icon:
            overrides["icon"] = self.icon_edit.text().strip()

        if allow_geometry:
            overrides["geometry"] = {
                "x": self.x_spin.value(),
                "y": self.y_spin.value(),
                "width": self.width_spin.value(),
                "height": self.height_spin.value(),
            }

        if allow_action:
            action_type = self.action_combo.currentData()
            action_target = self.action_target_edit.text().strip()
            if action_type != "none" and action_target:
                overrides["action"] = {"type": action_type, "value": action_target}
            else:
                overrides["action"] = {}

        self.window.apply_widget_overrides(key, overrides)
        if allow_geometry and overrides.get("geometry"):
            self.window.apply_geometry_override(key, overrides.get("geometry", {}))
        style_preview = overrides.get("style") or self.window._widget_defaults.get(key, {}).get("style", "")
        self.preview.setPlainText(style_preview)

    def _reset_widget(self) -> None:
        current_item = self.widget_list.currentItem()
        key = current_item.data(Qt.UserRole) if current_item else None
        if key is None:
            return
        self.window.apply_widget_overrides(key, {})
        self._load_widget_state(key)

    def _add_dynamic_button(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Add button")
        form = QFormLayout(dialog)
        text_edit = QLineEdit(dialog)
        icon_edit = QLineEdit(dialog)
        parent_combo = QComboBox(dialog)
        for parent_key in self.window.get_dynamic_parents():
            parent_combo.addItem(parent_key, parent_key)
        if parent_combo.count() == 0:
            parent_combo.addItem("top_toolbar", "top_toolbar")
        action_combo = QComboBox(dialog)
        action_combo.addItem("Sem ação extra", "none")
        action_combo.addItem("Abrir URL", "url")
        action_combo.addItem("Abrir arquivo", "file")
        action_combo.addItem("Chamar método", "method")
        action_combo.addItem("Abrir diálogo", "dialog")
        action_target_edit = QLineEdit(dialog)
        for label, field in (
            ("Texto", text_edit),
            ("Ícone", icon_edit),
            ("Painel", parent_combo),
            ("Ação", action_combo),
            ("Destino", action_target_edit),
        ):
            form.addRow(label, field)
        buttons = QHBoxLayout()
        ok_btn = QPushButton("Criar", dialog)
        cancel_btn = QPushButton("Cancelar", dialog)
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        form.addRow(buttons)
        if dialog.exec() == QDialog.Accepted:
            action_type = action_combo.currentData()
            action_target = action_target_edit.text().strip()
            action_cfg = {"type": action_type, "value": action_target} if action_type != "none" and action_target else {}
            new_id = self.window.create_dynamic_button(
                {
                    "text": text_edit.text().strip() or "Novo botão",
                    "icon": icon_edit.text().strip(),
                    "parent": parent_combo.currentData(),
                    "action": action_cfg,
                }
            )
            self._refresh_catalog(select_key=new_id)
