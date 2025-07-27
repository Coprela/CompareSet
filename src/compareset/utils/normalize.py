from __future__ import annotations

"""Helpers for aligning PDF coordinate spaces."""

from dataclasses import dataclass
from typing import List
import logging

import fitz
from pdf_diff import InvalidDimensionsError

logger = logging.getLogger(__name__)


@dataclass
class PageTransform:
    """Information about a single page transformation."""

    scale: float
    tx: float
    ty: float


@dataclass
class NormalizedPDF:
    """Normalized PDF and applied transformations."""

    document: fitz.Document
    transforms: List[PageTransform]


def _content_bbox(page: fitz.Page) -> fitz.Rect | None:
    """Return the bounding box of all drawn/text elements on ``page``."""
    boxes: List[fitz.Rect] = []
    # vector drawings
    for drawing in page.get_drawings():
        r = drawing.get("rect")
        if not r:
            xs = []
            ys = []
            for item in drawing.get("items", []):
                for point in item[1:]:
                    if isinstance(point, (list, tuple)) and len(point) >= 2:
                        xs.append(point[0])
                        ys.append(point[1])
            if xs and ys:
                r = fitz.Rect(min(xs), min(ys), max(xs), max(ys))
        if r:
            boxes.append(fitz.Rect(r))
    # images
    for img in page.get_images(full=True):
        xref = img[0]
        for rect in page.get_image_rects(xref):
            boxes.append(fitz.Rect(rect))
    # text blocks
    for block in page.get_text("dict").get("blocks", []):
        boxes.append(fitz.Rect(block["bbox"]))
    if not boxes:
        return None
    rect = boxes[0]
    for b in boxes[1:]:
        rect |= b
    return rect


def normalize_pdf_to_reference(pdf_ref_path: str, pdf_target_path: str) -> NormalizedPDF:
    """Adjust ``pdf_target_path`` to match ``pdf_ref_path`` coordinate space."""
    with fitz.open(pdf_ref_path) as doc_ref, fitz.open(pdf_target_path) as doc_tgt:
        result = fitz.open()
        transforms: List[PageTransform] = []
        max_pages = max(len(doc_ref), len(doc_tgt))
        for i in range(max_pages):
            ref_page = doc_ref[i] if i < len(doc_ref) else None
            tgt_page = doc_tgt[i] if i < len(doc_tgt) else None

            for p in (ref_page, tgt_page):
                if p and (p.rect.width <= 0 or p.rect.height <= 0):
                    logger.error(
                        "Invalid PDF dimensions on page %d: %.2fx%.2f",
                        i,
                        p.rect.width,
                        p.rect.height,
                    )
                    raise InvalidDimensionsError(
                        f"Invalid page dimensions: {p.rect.width}x{p.rect.height}"
                    )

            if ref_page is None and tgt_page is None:
                # nothing to do
                continue

            if ref_page is None:
                page_out = result.new_page(width=tgt_page.rect.width, height=tgt_page.rect.height)
                page_out.show_pdf_page(page_out.rect, doc_tgt, i)
                transforms.append(PageTransform(1.0, 0.0, 0.0))
                logger.debug("Page %d: no reference page, copied as is", i)
                continue

            if tgt_page is None:
                result.new_page(width=ref_page.rect.width, height=ref_page.rect.height)
                transforms.append(PageTransform(1.0, 0.0, 0.0))
                logger.debug("Page %d: missing target page, inserted blank", i)
                continue

            ref_bbox = _content_bbox(ref_page) or ref_page.rect
            tgt_bbox = _content_bbox(tgt_page) or tgt_page.rect

            if tgt_bbox.width == 0 or tgt_bbox.height == 0:
                scale = 1.0
                tx = ty = 0.0
                dest_size = ref_page.rect
            else:
                sx = ref_bbox.width / tgt_bbox.width
                sy = ref_bbox.height / tgt_bbox.height
                scale = min(sx, sy)
                tx = ref_bbox.x0 - tgt_bbox.x0 * scale
                ty = ref_bbox.y0 - tgt_bbox.y0 * scale
                tx += (ref_bbox.width - tgt_bbox.width * scale) / 2
                ty += (ref_bbox.height - tgt_bbox.height * scale) / 2
                dest_size = fitz.Rect(
                    tx,
                    ty,
                    tx + tgt_page.rect.width * scale,
                    ty + tgt_page.rect.height * scale,
                )

            logger.debug("Page %d: scale=%.3f, tx=%.3f, ty=%.3f", i, scale, tx, ty)
            page_out = result.new_page(width=ref_page.rect.width, height=ref_page.rect.height)
            page_out.show_pdf_page(dest_size, doc_tgt, i)
            transforms.append(PageTransform(scale, tx, ty))
        result.set_metadata(doc_tgt.metadata)
        return NormalizedPDF(result, transforms)
