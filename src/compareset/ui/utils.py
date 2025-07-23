from __future__ import annotations

from PySide6.QtCore import Qt, QFile
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtUiTools import QUiLoader


def load_svg_icon(path: str, size: int = 16) -> QIcon:
    """Load an SVG icon using QSvgRenderer for consistent scaling."""
    renderer = QSvgRenderer(path)
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    return QIcon(pix)


def load_ui(path: str, parent=None):
    """Load a .ui file produced by Qt Designer."""
    loader = QUiLoader()
    file = QFile(path)
    file.open(QFile.ReadOnly)
    ui = loader.load(file, parent)
    file.close()
    return ui
