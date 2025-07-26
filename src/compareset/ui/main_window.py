from __future__ import annotations

import os
from PySide6.QtWidgets import (
    QMainWindow,
    QStackedWidget,
    QToolBar,
    QStatusBar,
    QWidget,
    QPushButton,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, QPropertyAnimation

from .utils import load_icon, asset_path
from .compare_page import ComparePage
from .history_page import HistoryPage
from .admin_page import AdminPage
from .settings_dialog import SettingsDialog
from ..utils import normalize_pdf_to_reference

TRANSLATIONS = {
    "en": {"history": "History", "help": "Help", "settings": "Settings"},
    "pt": {"history": "Hist\u00f3rico", "help": "Ajuda", "settings": "Configura\u00e7\u00f5es"},
}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CompareSet")
        self.resize(800, 600)

        self.lang = "en"
        self.theme = "light"

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.compare_page = ComparePage(self)
        self.history_page = HistoryPage(self)
        self.admin_page = AdminPage(self)

        self.stack.addWidget(self.compare_page)
        self.stack.addWidget(self.history_page)
        self.stack.addWidget(self.admin_page)

        self._create_toolbar()
        self.setStatusBar(QStatusBar())
        self._add_test_button()

        self.set_language(self.lang)
        self.apply_theme(self.theme)

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
        self.compare_page.set_language(self.lang)

    def apply_theme(self, theme: str) -> None:
        self.theme = theme if theme in ("light", "dark") else "light"
        fname = "style.qss" if self.theme == "light" else "style_dark.qss"
        path = os.path.join(asset_path(), fname)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.window().setStyleSheet(f.read())

    def open_help(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(self, "Help", "Help is not implemented yet")

    def open_settings(self) -> None:
        dlg = SettingsDialog(self)
        dlg.set_language(self.lang)
        dlg.exec()

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
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
