"""Generate simple colored overlays for PDF pages."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import fitz

from .compare import DiffResult, PageDiff


@dataclass(frozen=True)
class AnnotationStyle:
    stroke_color: tuple[float, float, float]
    stroke_width: float = 0.8
    fill_color: tuple[float, float, float] = (0.93, 0.93, 0.93)
    fill_opacity: float = 0.15


def annotate_pdf(
    result: DiffResult,
    *,
    source_pdf: str | Path,
    output_pdf: str | Path,
    change_type: str,
    style: AnnotationStyle,
) -> None:
    """Render annotations for a specific change type on a PDF copy."""

    page_map = {page.index: page for page in result.pages}
    output_path = Path(output_pdf)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(source_pdf))
    try:
        _draw_annotations(doc, page_map.values(), change_type, style)
        doc.save(str(output_pdf))
    finally:
        doc.close()


def _draw_annotations(
    doc: fitz.Document,
    pages: Iterable[PageDiff],
    change_type: str,
    style: AnnotationStyle,
) -> None:
    for page_diff in pages:
        if page_diff.index >= len(doc):
            continue
        page = doc[page_diff.index]
        relevant = [region for region in page_diff.regions if region.change_type == change_type]
        if not relevant:
            continue
        shape = page.new_shape()
        for region in relevant:
            rect = fitz.Rect(*region.bbox_pdf)
            shape.draw_rect(rect)
            shape.finish(
                color=style.stroke_color,
                width=style.stroke_width,
                fill=style.fill_color,
                fill_opacity=style.fill_opacity,
            )
        shape.commit()
