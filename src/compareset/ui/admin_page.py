from __future__ import annotations

import os
from PySide6.QtWidgets import QWidget

from .utils import load_ui


class AdminPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        ui_path = os.path.join(os.path.dirname(__file__), 'admin_page.ui')
        load_ui(ui_path, self)
