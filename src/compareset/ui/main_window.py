from __future__ import annotations

import os
from PySide6.QtWidgets import (
    QMainWindow,
    QStackedWidget,
    QToolBar,
    QStatusBar,
    QWidget,
    QToolButton,
    QMenu,
    QPushButton,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, QPropertyAnimation

from .utils import load_icon, asset_path
from .compare_page import ComparePage
from .history_page import HistoryPage
from .admin_page import AdminPage
from .settings_page import SettingsPage
from ..utils import normalize_pdf_to_reference

TRANSLATIONS = {
    "en": {"history": "History", "help": "Help", "settings": "Settings", "language": "Language"},
    "pt": {"history": "Hist\u00f3rico", "help": "Ajuda", "settings": "Configura\u00e7\u00f5es", "language": "Idioma"},
}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CompareSet")
        self.resize(800, 600)

        self.lang = "en"

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.compare_page = ComparePage(self)
        self.history_page = HistoryPage(self)
        self.admin_page = AdminPage(self)
        self.settings_page = SettingsPage(self)

        self.stack.addWidget(self.compare_page)
        self.stack.addWidget(self.history_page)
        self.stack.addWidget(self.admin_page)
        self.stack.addWidget(self.settings_page)

        self._create_toolbar()
        self.setStatusBar(QStatusBar())
        self._add_test_button()

        self.set_language(self.lang)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar()
        toolbar.setMovable(False)
        icon_dir = asset_path("icons")
        self.action_history = toolbar.addAction(
            load_icon(os.path.join(icon_dir, "Icon - History.png")),
            "",
            lambda: self.switch_page(self.history_page),
        )
        self.action_history.setToolTip("History")
        self.action_settings = toolbar.addAction(
            load_icon(os.path.join(icon_dir, "Icon - Gear.png")), ""
        )
        self.action_settings.setToolTip("Settings")
        self.action_help = toolbar.addAction(
            load_icon(os.path.join(icon_dir, "Icon - Question Mark Help.png")), ""
        )
        self.action_help.setToolTip("Help")

        self.action_history.triggered.connect(
            lambda: self.switch_page(self.history_page)
        )
        self.action_settings.triggered.connect(
            self.open_settings
        )
        self.action_help.triggered.connect(self.open_help)

        # language toggle button
        self.lang_button = QToolButton()
        lang_menu = QMenu(self.lang_button)
        act_en = lang_menu.addAction("EN")
        act_pt = lang_menu.addAction("PT")
        act_en.triggered.connect(lambda: self.set_language("en"))
        act_pt.triggered.connect(lambda: self.set_language("pt"))
        self.lang_button.setMenu(lang_menu)
        self.lang_button.setPopupMode(QToolButton.InstantPopup)
        toolbar.addWidget(self.lang_button)

        self.addToolBar(toolbar)

    def _add_test_button(self) -> None:
        btn = QPushButton("Test Normalization")
        self.statusBar().addPermanentWidget(btn)
        btn.clicked.connect(self._run_normalization_test)
        self._test_btn = btn

    def set_language(self, lang: str) -> None:
        """Set interface language and update labels."""
        self.lang = lang if lang in TRANSLATIONS else "en"
        t = TRANSLATIONS[self.lang]
        self.action_history.setText(t["history"])
        self.action_history.setToolTip(t["history"])
        self.action_help.setText(t["help"])
        self.action_help.setToolTip(t["help"])
        self.action_settings.setText(t["settings"])
        self.action_settings.setToolTip(t["settings"])
        self.lang_button.setText(t["language"])
        self.compare_page.set_language(self.lang)
        self.settings_page.set_language(self.lang)

    def open_help(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(self, "Help", "Help is not implemented yet")

    def open_settings(self) -> None:
        self.switch_page(self.settings_page)

    def switch_page(self, page: QWidget) -> None:
        self.statusBar().showMessage(page.objectName(), 2000)
        self.stack.setCurrentWidget(page)
        anim = QPropertyAnimation(page, b"windowOpacity")
        anim.setDuration(200)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()

    def _run_normalization_test(self) -> None:
        ref, _ = QFileDialog.getOpenFileName(self, "Reference PDF", filter="PDF Files (*.pdf)")
        if not ref:
            return
        tgt, _ = QFileDialog.getOpenFileName(self, "Target PDF", filter="PDF Files (*.pdf)")
        if not tgt:
            return
        result = normalize_pdf_to_reference(ref, tgt)
        save, _ = QFileDialog.getSaveFileName(self, "Save normalized PDF", filter="PDF Files (*.pdf)")
        if save:
            result.document.save(save)
        msg = "\n".join(
            f"page {i}: scale={t.scale:.3f} tx={t.tx:.3f} ty={t.ty:.3f}" for i, t in enumerate(result.transforms)
        )
        QMessageBox.information(self, "Normalization", msg)


def main() -> None:
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    style_path = os.path.join(asset_path(), "style.qss")
    if os.path.exists(style_path):
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
