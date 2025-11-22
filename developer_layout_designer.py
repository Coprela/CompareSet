"""No-code layout designer for CompareSet developer mode."""
from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
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
        self.setMinimumSize(520, 420)
        self._build_ui()

        if self.widget_list.count():
            self.widget_list.setCurrentRow(0)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Arraste os painéis usando o modo Layout Editor. Aqui você pode alterar textos, "
                "cores e tamanhos sem programar. Selecione um elemento, edite e clique em Apply."
            )
        )

        self.widget_list = QListWidget()
        for key, info in self.catalog.items():
            item = QListWidgetItem(str(info.get("display_name", key)))
            item.setData(Qt.UserRole, key)
            self.widget_list.addItem(item)
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

        form.addRow("Texto", self.text_edit)
        form.addRow("Tamanho da fonte", self.font_size_spin)
        form.addRow("", self.bold_checkbox)
        form.addRow("Cor do texto", self.color_edit)
        form.addRow("Fundo", self.background_edit)
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

    def _on_selection_changed(self, current: Optional[QListWidgetItem]) -> None:
        key = current.data(Qt.UserRole) if current else None
        self._load_widget_state(key)

    def _load_widget_state(self, key: Optional[str]) -> None:
        info = self.catalog.get(key or "", {})
        defaults = self.window._widget_defaults.get(key or "", {})
        overrides = self.window._widget_overrides.get(key or "", {})
        allow_text = bool(info.get("allow_text", True))
        allow_style = bool(info.get("allow_style", True))

        current_text = overrides.get("text") or defaults.get("text") or ""
        self.text_edit.setText(current_text)
        self.text_edit.setEnabled(allow_text)
        self.font_size_spin.setEnabled(allow_style)
        self.bold_checkbox.setEnabled(allow_style)
        self.color_edit.setEnabled(allow_style)
        self.background_edit.setEnabled(allow_style)
        self.preview.setEnabled(allow_style)

        style_source = overrides.get("style") or defaults.get("style") or ""
        parsed_style = self._parse_style(style_source)
        self.font_size_spin.setValue(parsed_style.get("font_size", 0))
        self.bold_checkbox.setChecked(parsed_style.get("bold", False))
        self.color_edit.setText(parsed_style.get("color", ""))
        self.background_edit.setText(parsed_style.get("background", ""))
        self.preview.setPlainText(style_source.strip())

    def _parse_style(self, style: str) -> Dict[str, str | int | bool]:
        parsed: Dict[str, str | int | bool] = {}
        tokens = [segment.strip() for segment in style.split(";") if segment.strip()]
        for token in tokens:
            if token.startswith("color:"):
                parsed["color"] = token.split(":", 1)[1].strip()
            elif token.startswith("background-color:"):
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
        base_style = defaults.get("style") or ""
        if not rules:
            return None
        style_parts = [base_style.strip()] if base_style.strip() else []
        style_parts.append(" ".join(rules))
        return "\n".join(style_parts).strip()

    def _apply_changes(self) -> None:
        current_item = self.widget_list.currentItem()
        key = current_item.data(Qt.UserRole) if current_item else None
        if key is None:
            return
        info = self.catalog.get(key, {})
        allow_text = bool(info.get("allow_text", True))
        allow_style = bool(info.get("allow_style", True))
        defaults = self.window._widget_defaults.get(key, {})

        overrides: Dict[str, str] = {}
        new_text = self.text_edit.text()
        if allow_text and new_text != defaults.get("text"):
            overrides["text"] = new_text

        style_override = self._build_style(defaults) if allow_style else None
        if allow_style and style_override:
            overrides["style"] = style_override

        self.window.apply_widget_overrides(key, overrides)
        style_preview = overrides.get("style") or self.window._widget_defaults.get(key, {}).get("style", "")
        self.preview.setPlainText(style_preview)

    def _reset_widget(self) -> None:
        current_item = self.widget_list.currentItem()
        key = current_item.data(Qt.UserRole) if current_item else None
        if key is None:
            return
        self.window.apply_widget_overrides(key, {})
        self._load_widget_state(key)
