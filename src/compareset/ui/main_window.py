from __future__ import annotations

import os
from PySide6.QtWidgets import (
    QMainWindow,
    QStackedWidget,
    QToolBar,
    QStatusBar,
    QWidget,
)
from PySide6.QtCore import Qt, QPropertyAnimation

from .utils import load_svg_icon
from .compare_page import ComparePage
from .history_page import HistoryPage
from .admin_page import AdminPage


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CompareSet")
        self.resize(800, 600)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.compare_page = ComparePage()
        self.history_page = HistoryPage()
        self.admin_page = AdminPage()

        self.stack.addWidget(self.compare_page)
        self.stack.addWidget(self.history_page)
        self.stack.addWidget(self.admin_page)

        self._create_toolbar()
        self.setStatusBar(QStatusBar())

    def _create_toolbar(self) -> None:
        toolbar = QToolBar()
        toolbar.setMovable(False)
        icon_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'icons')
        toolbar.addAction(load_svg_icon(os.path.join(icon_dir, 'history.svg')), "History", lambda: self.switch_page(self.history_page)).setToolTip("History")
        toolbar.addAction(load_svg_icon(os.path.join(icon_dir, 'settings.svg')), "Settings").setToolTip("Settings")
        toolbar.addAction(load_svg_icon(os.path.join(icon_dir, 'help.svg')), "Help").setToolTip("Help")
        self.addToolBar(toolbar)

    def switch_page(self, page: QWidget) -> None:
        self.statusBar().showMessage(page.objectName(), 2000)
        self.stack.setCurrentWidget(page)
        anim = QPropertyAnimation(page, b"windowOpacity")
        anim.setDuration(200)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()


def main() -> None:
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    style_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'style.qss')
    if os.path.exists(style_path):
        with open(style_path, 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
