from __future__ import annotations

from pathlib import Path
import sys
from PySide6.QtCore import QFile
from PySide6.QtGui import QIcon
from PySide6.QtUiTools import QUiLoader


def load_icon(path: str) -> QIcon:
    """Load a PNG icon."""
    return QIcon(path)


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
    """Load a .ui file produced by Qt Designer.

    When ``parent`` is provided the loaded widget's layout and children
    are re-parented so that ``parent`` effectively becomes the top-level
    widget. This mirrors the behaviour of :func:`uic.loadUi` and ensures
    the UI elements are visible even when ``parent`` has no layout set.
    """

    loader = QUiLoader()
    file = QFile(path)
    if not file.exists():
        raise FileNotFoundError(path)

    file.open(QFile.ReadOnly)
    ui = loader.load(file, parent)
    file.close()

    if parent is not None and ui is not parent:
        layout = ui.layout()
        if layout is not None:
            parent.setLayout(layout)
        for child in ui.children():
            if hasattr(child, "setParent"):
                child.setParent(parent)
        ui.deleteLater()
        return parent

    return ui
