"""Minimal extraction utilities using PyMuPDF.

This module provides a very small subset of the eventual extraction
capabilities.  For the purposes of the tests we only need to collect
basic information about stroked path objects so that they can be mapped
back to their drawing operations within the PDF stream.
"""
from __future__ import annotations

from typing import List

import fitz  # PyMuPDF

from .types import GraphicObject, PaintMode


def extract_page_objects(doc: fitz.Document, page_index: int) -> List[GraphicObject]:
    """Extract simple path objects from a page.

    The real project aims to support a wide variety of PDF graphic
    constructs.  The minimal implementation here focuses purely on
    stroked paths that originate directly in the page content stream.  It
    uses :meth:`Page.get_drawings` which returns a convenient summary of
    path drawing commands.
    """

    page = doc[page_index]
    objects: List[GraphicObject] = []

    drawings = page.get_drawings()
    for seq, draw in enumerate(drawings):
        bbox = tuple(draw["rect"])
        stroke_color = draw.get("color")
        fill_color = draw.get("fill")
        if stroke_color and fill_color:
            paint_mode: PaintMode = "both"
        elif stroke_color:
            paint_mode = "stroke"
        elif fill_color:
            paint_mode = "fill"
        else:
            # No paint, skip
            continue

        obj = GraphicObject(
            obj_id=f"p{page_index}_obj{seq}",
            kind="path",
            page_index=page_index,
            bbox=bbox,  # type: ignore[arg-type]
            paint_mode=paint_mode,
            linewidth=draw.get("width"),
            stroke_color=stroke_color,
            fill_color=fill_color,
            ctm=(1, 0, 0, 1, 0, 0),  # page coordinates already
            stream_ref=f"page:{page_index}",
            ops_hint=(draw.get("seqno", seq), len(draw.get("items", []))),
        )
        objects.append(obj)

    return objects
