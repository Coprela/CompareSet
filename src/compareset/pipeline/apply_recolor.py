"""High level helper to recolor PDFs given diff information.

This is a very small façade combining extraction, diff bridging and the
low level editing utilities.  It is intentionally simple and geared
solely towards the unit tests in this kata.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import fitz

from ..core import diff_bridge, extraction, pdf_edit
from ..core.types import DiffKind


def apply_recolor(pdf_path: Path, diff_map: Dict[str, DiffKind], out_path: Path) -> None:
    """Recolor selected objects in ``pdf_path`` and save to ``out_path``."""

    doc = fitz.open(pdf_path)
    targets_for_pages: Dict[int, list] = {}
    for page_index in range(doc.page_count):
        objs = extraction.extract_page_objects(doc, page_index)
        targets = diff_bridge.build_targets(objs, diff_map)
        if targets:
            targets_for_pages[page_index] = targets
    doc.close()
    pdf_edit.recolor_targets_in_pdf(str(pdf_path), str(out_path), targets_for_pages)
