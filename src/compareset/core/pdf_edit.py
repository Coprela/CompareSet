"""PDF in-place recoloring utilities.

This minimal implementation uses PyMuPDF to edit content streams.  It is
purposefully limited – only stroked paths within page content streams are
supported.  The aim is merely to demonstrate the core idea for the unit
tests in this kata.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

import fitz

from .types import PaintMode, Target

log = logging.getLogger(__name__)


STROKE_RE = re.compile(r"\bS\b")


def recolor_targets_in_pdf(
    in_path: str,
    out_path: str,
    targets_for_pages: Dict[int, List[Target]],
    rgb_added: Tuple[float, float, float] = (0, 1, 0),
    rgb_removed: Tuple[float, float, float] = (1, 0, 0),
) -> None:
    """Open ``in_path`` PDF and recolor targets, saving to ``out_path``."""

    doc = fitz.open(in_path)
    for page_index, targets in targets_for_pages.items():
        page = doc[page_index]
        successes = 0
        for tgt in targets:
            rgb = rgb_removed if tgt.diff == "removed" else rgb_added
            if inject_color_in_stream(doc, page, tgt.stream_ref, tgt.ops_hint, rgb, None, tgt.paint_mode):
                successes += 1
        log.info("page %s recolored %s/%s objects", page_index, successes, len(targets))
    doc.save(out_path)


def inject_color_in_stream(
    doc: fitz.Document,
    page: fitz.Page,
    stream_ref: str,
    ops_hint: Optional[Tuple[int, int]],
    rgb_stroke: Optional[Tuple[float, float, float]],
    rgb_fill: Optional[Tuple[float, float, float]],
    paint_mode: PaintMode,
) -> bool:
    """Insert colour operators around an ``S`` stroke command.

    The implementation only edits the first content stream of ``page`` and
    is limited to stroke recolouring.
    """

    if paint_mode not in ("stroke", "both"):
        return False
    if not rgb_stroke:
        return False

    contents = page.get_contents()
    if not contents:
        return False
    xref = contents[0]
    stream = doc.xref_stream(xref).decode("latin-1")

    matches = list(STROKE_RE.finditer(stream))
    ord_index = ops_hint[0] if ops_hint else 0
    if ord_index >= len(matches):
        return False
    m = matches[ord_index]
    r, g, b = rgb_stroke
    injection = f"q {r} {g} {b} RG\n"
    new_stream = stream[: m.start()] + injection + stream[m.start() : m.end()] + "\nQ" + stream[m.end() :]
    doc.update_stream(xref, new_stream.encode("latin-1"))
    return True


def clone_form_xobject_if_needed(doc: fitz.Document, xobj_name: str) -> str:
    """Placeholder for future form XObject cloning support."""

    return xobj_name
