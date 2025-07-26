from __future__ import annotations

import os
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QHBoxLayout,
)

from .utils import asset_path, root_path

TRANSLATIONS = {
    "en": {
        "language": "Language",
        "appearance": "Appearance",
        "apply": "Apply",
        "light": "Light",
        "dark": "Dark",
        "license": "License",
        "not_found": "License file not found.",
    },
    "pt": {
        "language": "Idioma",
        "appearance": "Apar\u00eancia",
        "apply": "Aplicar",
        "light": "Claro",
        "dark": "Escuro",
        "license": "Licen\u00e7a",
        "not_found": "Arquivo de licen\u00e7a n\u00e3o encontrado.",
    },
}


class SettingsDialog(QDialog):
    def __init__(self, main: 'MainWindow') -> None:
        super().__init__(main)
        self.main = main
        self.setWindowTitle(self.main.tr("settings"))

        layout = QVBoxLayout(self)

        self.lang_label = QLabel()
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English (US)", "en")
        self.lang_combo.addItem("Portugu\u00eas (Brasil)", "pt")
        layout.addWidget(self.lang_label)
        layout.addWidget(self.lang_combo)

        self.appearance_label = QLabel()
        self.appearance_combo = QComboBox()
        self.appearance_combo.addItem(TRANSLATIONS["en"]["light"], "light")
        self.appearance_combo.addItem(TRANSLATIONS["en"]["dark"], "dark")
        layout.addWidget(self.appearance_label)
        layout.addWidget(self.appearance_combo)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.apply_btn = QPushButton()
        self.ok_btn = QPushButton("OK")
        btn_row.addWidget(self.apply_btn)
        btn_row.addWidget(self.ok_btn)
        layout.addLayout(btn_row)

        self.apply_btn.clicked.connect(self.apply_settings)
        self.ok_btn.clicked.connect(lambda: (self.apply_settings(), self.accept()))

        self.set_language(self.main.lang)
        self.load_state()

    def load_state(self) -> None:
        self.lang_combo.setCurrentIndex(0 if self.main.lang == "en" else 1)
        self.appearance_combo.setCurrentIndex(0 if self.main.theme == "light" else 1)

    def set_language(self, lang: str) -> None:
        t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
        self.lang_label.setText(t["language"])
        self.appearance_label.setText(t["appearance"])
        self.apply_btn.setText(t["apply"])
        self.appearance_combo.setItemText(0, t["light"])
        self.appearance_combo.setItemText(1, t["dark"])
        self.lang_combo.setItemText(0, "English (US)")
        self.lang_combo.setItemText(1, "Portugu\u00eas (Brasil)")

    def apply_settings(self) -> None:
        lang = self.lang_combo.currentData()
        theme = self.appearance_combo.currentData()
        self.main.set_language(lang)
        self.main.apply_theme(theme)

    def show_license(self) -> None:
        fname = "LICENSE_EN.txt" if self.main.lang == "en" else "LICENSE_PT.txt"
        path = root_path(fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception:
            t = TRANSLATIONS.get(self.main.lang, TRANSLATIONS["en"])
            text = t["not_found"]
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(self, "License", text)
