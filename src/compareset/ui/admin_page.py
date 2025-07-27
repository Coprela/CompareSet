from __future__ import annotations

import os
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHBoxLayout,
)

from .utils import load_ui


class AdminPage(QWidget):
    def __init__(self, main: 'MainWindow') -> None:
        super().__init__(parent=main.stack)
        self.main = main
        ui_path = os.path.join(os.path.dirname(__file__), 'admin_page.ui')
        load_ui(ui_path, self)
        layout = self.layout()
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["User", "Email", "Role"])
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("Add User")
        self.reset_btn = QPushButton("Reset Password")
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.reset_btn)
        layout.addLayout(btn_row)

        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(lambda: self.main.switch_page(self.main.compare_page))
        layout.addWidget(self.back_btn)
        self.load_placeholder()

    def load_placeholder(self) -> None:
        self.table.setRowCount(2)
        self.table.setItem(0, 0, QTableWidgetItem("admin"))
        self.table.setItem(0, 1, QTableWidgetItem("admin@example.com"))
        self.table.setItem(0, 2, QTableWidgetItem("Admin"))
        self.table.setItem(1, 0, QTableWidgetItem("user"))
        self.table.setItem(1, 1, QTableWidgetItem("user@example.com"))
        self.table.setItem(1, 2, QTableWidgetItem("User"))
