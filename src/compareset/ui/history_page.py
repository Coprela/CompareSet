from __future__ import annotations

import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton

from .utils import load_ui


class HistoryPage(QWidget):
    def __init__(self, main: 'MainWindow') -> None:
        super().__init__(parent=main.stack)
        self.main = main
        ui_path = os.path.join(os.path.dirname(__file__), 'history_page.ui')
        load_ui(ui_path, self)
        layout = self.layout()
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["File", "Date", "Status"])
        layout.addWidget(self.table)
        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(lambda: self.main.switch_page(self.main.compare_page))
        layout.addWidget(self.back_btn)
        self.load_placeholder()

    def load_placeholder(self) -> None:
        self.table.setRowCount(3)
        for i in range(3):
            self.table.setItem(i, 0, QTableWidgetItem(f"result_{i}.pdf"))
            self.table.setItem(i, 1, QTableWidgetItem("2023-01-01"))
            self.table.setItem(i, 2, QTableWidgetItem("ok"))
