import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QFile
from PySide6.QtUiTools import QUiLoader

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

UI_DIR = Path("src/compareset/ui")
UI_FILES = [
    UI_DIR / name for name in ["compare_page.ui", "history_page.ui", "admin_page.ui"]
]


@pytest.mark.parametrize("ui_file", UI_FILES)
def test_ui_file_loads(ui_file):
    loader = QUiLoader()
    file = QFile(str(ui_file))
    assert file.open(QFile.ReadOnly)
    widget = loader.load(file)
    file.close()
    assert widget is not None
