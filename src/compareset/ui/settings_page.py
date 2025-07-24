from __future__ import annotations

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton
)

from .utils import asset_path

TRANSLATIONS = {
    "en": {"language": "Language", "appearance": "Appearance", "back": "Back", "license": "License", "light": "Light", "dark": "Dark"},
    "pt": {"language": "Idioma", "appearance": "Aparência", "back": "Voltar", "license": "Licença", "light": "Claro", "dark": "Escuro"},
}


class SettingsPage(QWidget):
    def __init__(self, main: 'MainWindow') -> None:
        super().__init__(parent=main.stack)
        self.main = main
        layout = QVBoxLayout(self)

        self.lang_label = QLabel()
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("Português", "pt")
        layout.addWidget(self.lang_label)
        layout.addWidget(self.lang_combo)

        self.appearance_label = QLabel()
        self.appearance_combo = QComboBox()
        self.appearance_combo.addItem("Light", "light")
        self.appearance_combo.addItem("Dark", "dark")
        layout.addWidget(self.appearance_label)
        layout.addWidget(self.appearance_combo)

        self.license_btn = QPushButton()
        self.license_btn.clicked.connect(self.show_license)
        layout.addWidget(self.license_btn)

        self.back_btn = QPushButton()
        self.back_btn.clicked.connect(lambda: self.main.switch_page(self.main.compare_page))
        layout.addWidget(self.back_btn)

        self.set_language(self.main.lang)

    def set_language(self, lang: str) -> None:
        t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
        self.lang_label.setText(t["language"])
        idx = 0 if lang == "en" else 1
        self.lang_combo.setCurrentIndex(idx)
        self.appearance_label.setText(t["appearance"])
        self.license_btn.setText(t["license"])
        self.back_btn.setText(t["back"])
        self.appearance_combo.setItemText(0, t["light"])
        self.appearance_combo.setItemText(1, t["dark"])

    def show_license(self) -> None:
        fname = "LICENSE_EN.txt" if self.main.lang == "en" else "LICENSE_PT.txt"
        path = os.path.join(asset_path(), fname)
        text = ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception:
            text = "License file not found."
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(self, "License", text)
