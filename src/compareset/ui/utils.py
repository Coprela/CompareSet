from __future__ import annotations

from pathlib import Path
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


def asset_path(*parts: str) -> str:
    """Return absolute path to an asset, working in dev and installed modes."""
    base = Path(__file__).resolve()
    # Check repository layout first (../..../assets)
    candidate = base.parents[3] / "assets" / Path(*parts)
    if candidate.exists():
        return str(candidate)
    # Fallback to installed package layout (..../assets)
    candidate = base.parents[2] / "assets" / Path(*parts)
    return str(candidate)


def load_ui(path: str, parent=None):
    """Load a .ui file produced by Qt Designer."""
    loader = QUiLoader()
    file = QFile(path)
    file.open(QFile.ReadOnly)
    ui = loader.load(file, parent)
    file.close()
    return ui
