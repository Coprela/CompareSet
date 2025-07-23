from __future__ import annotations

from pathlib import Path
import sys
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
    """Return absolute path to an asset in all supported environments."""
    base = Path(__file__).resolve()

    # When packaged with PyInstaller the assets are extracted to ``_MEIPASS``.
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base:
        candidate = Path(frozen_base) / "assets" / Path(*parts)
        if candidate.exists():
            return str(candidate)

    # Repository layout (src/compareset/... -> ../../assets)
    candidate = base.parents[3] / "assets" / Path(*parts)
    if candidate.exists():
        return str(candidate)

    # Installed package layout (.../site-packages/compareset/... -> ../assets)
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
