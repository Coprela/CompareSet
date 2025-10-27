"""PDF overlay generation using PyMuPDF."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import fitz

from .compare import DiffResult, DiffRegion, PageDiff
from .presets import ColorScheme


@dataclass(frozen=True)
class OverlayOptions:
    fill_opacity: float = 0.22
    stroke_width: float = 1.0
    legend: bool = True
    bookmarks: bool = True


def draw_overlays(
    result: DiffResult,
    *,
    source_pdf: str,
    output_pdf: str,
    colors: ColorScheme,
    options: OverlayOptions,
) -> None:
    Path(output_pdf).parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(source_pdf)
    try:
        _draw_regions(doc, result.pages, colors, options)
        if options.legend and len(doc) > 0:
            _draw_legend(doc[0], colors, result)
        if options.bookmarks:
            _apply_bookmarks(doc, result.pages)
        doc.save(output_pdf)
    finally:
        doc.close()


def _draw_regions(
    doc: fitz.Document,
    pages: Iterable[PageDiff],
    colors: ColorScheme,
    options: OverlayOptions,
) -> None:
    for page_result in pages:
        if page_result.index >= len(doc):
            continue
        page = doc[page_result.index]
        shape = page.new_shape()
        has_region = False
        for region in page_result.regions:
            rect = fitz.Rect(*region.bbox_pdf)
            stroke_color = _color_for_region(region, colors)
            fill_color = stroke_color
            shape.draw_rect(rect)
            shape.finish(
                color=stroke_color,
                fill=fill_color,
                fill_opacity=options.fill_opacity,
                width=options.stroke_width,
            )
            has_region = True
        if has_region:
            shape.commit()


def _color_for_region(region: DiffRegion, colors: ColorScheme):
    mapping = {
        "added": colors.added,
        "removed": colors.removed,
        "modified": colors.modified,
    }
    return mapping.get(region.change_type, colors.modified)


def _draw_legend(page: fitz.Page, colors: ColorScheme, result: DiffResult) -> None:
    margin = 24
    box_height = 14
    gap = 6
    legend_rect = fitz.Rect(
        page.rect.x0 + margin,
        page.rect.y0 + margin,
        page.rect.x0 + margin + 220,
        page.rect.y0 + margin + 4 * (box_height + gap) + 30,
    )
    shape = page.new_shape()
    shape.draw_rect(legend_rect)
    shape.finish(color=(0.7, 0.7, 0.7), fill=(1, 1, 1), fill_opacity=0.92, width=0.5)
    shape.commit()

    lines = ["CompareSet legend", "", _params_line(result)]
    entries = [
        ("Added", colors.added),
        ("Removed", colors.removed),
        ("Modified", colors.modified),
    ]
    y = legend_rect.y0 + 24
    for title, color in entries:
        swatch = fitz.Rect(legend_rect.x0 + 8, y - 6, legend_rect.x0 + 28, y + 6)
        page.draw_rect(swatch, color=color, fill=color, fill_opacity=0.22, width=0.5)
        lines.append(f"{title} regions")
        y += box_height + gap
    page.insert_textbox(
        legend_rect,
        "\n".join(lines),
        fontsize=8.5,
        fontname="helv",
        color=colors.text,
    )


def _params_line(result: DiffResult) -> str:
    params = result.params
    return (
        f"dpi={params.dpi} abs={params.absdiff_threshold} ssim={params.ssim_threshold} "
        f"min_area={params.min_area_px} merge_iou={params.merge_iou}"
    )


def _apply_bookmarks(doc: fitz.Document, pages: Iterable[PageDiff]) -> None:
    toc: List[List[int | str]] = []
    for page in pages:
        if not page.regions:
            continue
        toc.append([1, f"Page {page.index + 1} ({len(page.regions)} changes)", page.index + 1])
    if toc:
        doc.set_toc(toc)
