"""Core PDF comparison logic."""

from __future__ import annotations

import fitz
from typing import List, Tuple


BBox = Tuple[float, float, float, float]


def _extract_elements(page: fitz.Page, sx: float = 1.0, sy: float = 1.0) -> List[Tuple[fitz.Rect, str]]:
    """Return bounding boxes and associated text for text and vector elements."""
    elements: List[Tuple[fitz.Rect, str]] = []

    for word in page.get_text("words"):
        if len(word) >= 5:
            x0, y0, x1, y1, text = word[:5]
            rect = fitz.Rect(float(x0) * sx, float(y0) * sy, float(x1) * sx, float(y1) * sy)
            elements.append((rect, str(text).strip()))

    for drawing in page.get_drawings():
        r = drawing.get("rect")
        if not r:
            xs: List[float] = []
            ys: List[float] = []
            for item in drawing.get("items", []):
                for point in item[1:]:
                    if isinstance(point, (list, tuple)) and len(point) >= 2:
                        xs.append(float(point[0]))
                        ys.append(float(point[1]))
            if xs and ys:
                r = fitz.Rect(min(xs), min(ys), max(xs), max(ys))
        if r:
            rect = fitz.Rect(r.x0 * sx, r.y0 * sy, r.x1 * sx, r.y1 * sy)
            elements.append((rect, ""))

    for annot in page.annots() or []:
        r = annot.rect
        rect = fitz.Rect(r.x0 * sx, r.y0 * sy, r.x1 * sx, r.y1 * sy)
        elements.append((rect, ""))

    return elements


def _iou(a: fitz.Rect, b: fitz.Rect) -> float:
    """Intersection over Union between two rectangles."""
    x1 = max(a.x0, b.x0)
    y1 = max(a.y0, b.y0)
    x2 = min(a.x1, b.x1)
    y2 = min(a.y1, b.y1)
    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter = inter_w * inter_h
    if inter == 0:
        return 0.0
    area_a = (a.x1 - a.x0) * (a.y1 - a.y0)
    area_b = (b.x1 - b.x0) * (b.y1 - b.y0)
    return inter / float(area_a + area_b - inter)


def _compare_pages(old_page: fitz.Page, new_page: fitz.Page, thr: float) -> Tuple[List[Tuple[fitz.Rect, str]], List[Tuple[fitz.Rect, str]]]:
    """Compare two pages and return removed and added elements."""
    sx = old_page.rect.width / new_page.rect.width if new_page.rect.width else 1.0
    sy = old_page.rect.height / new_page.rect.height if new_page.rect.height else 1.0

    old_boxes = _extract_elements(old_page)
    new_boxes = _extract_elements(new_page, sx, sy)

    matched_new = set()
    removed = []
    added = []

    for obox, otext in old_boxes:
        found = False
        for idx, (nbox, ntext) in enumerate(new_boxes):
            if idx in matched_new:
                continue
            if _iou(obox, nbox) >= thr:
                matched_new.add(idx)
                found = True
                if otext != ntext:
                    removed.append((obox, otext))
                    added.append((nbox, ntext))
                break
        if not found:
            removed.append((obox, otext))

    for idx, (nbox, ntext) in enumerate(new_boxes):
        if idx not in matched_new:
            added.append((nbox, ntext))

    return removed, added


def compare_pdfs(old_pdf: str, new_pdf: str, thr: float = 0.95) -> Tuple[List[dict], List[dict]]:
    """Compare two PDFs and return lists of removed and added elements."""
    removidos: List[dict] = []
    adicionados: List[dict] = []
    with fitz.open(old_pdf) as doc_old, fitz.open(new_pdf) as doc_new:
        max_pages = max(len(doc_old), len(doc_new))
        for i in range(max_pages):
            if i >= len(doc_old):
                for nbox, ntext in _extract_elements(doc_new[i]):
                    adicionados.append({"page": i, "bbox": [nbox.x0, nbox.y0, nbox.x1, nbox.y1], "text": ntext})
                continue
            if i >= len(doc_new):
                for obox, otext in _extract_elements(doc_old[i]):
                    removidos.append({"page": i, "bbox": [obox.x0, obox.y0, obox.x1, obox.y1], "text": otext})
                continue
            rem, add = _compare_pages(doc_old[i], doc_new[i], thr)
            for box, text in rem:
                removidos.append({"page": i, "bbox": [box.x0, box.y0, box.x1, box.y1], "text": text})
            for box, text in add:
                adicionados.append({"page": i, "bbox": [box.x0, box.y0, box.x1, box.y1], "text": text})
    return removidos, adicionados


def generate_highlighted_pdf(
    old_pdf: str,
    new_pdf: str,
    removed: List[dict],
    added: List[dict],
    output_pdf: str,
    color_remove: Tuple[float, float, float] = (1, 0, 0),
    color_add: Tuple[float, float, float] = (0, 1, 0),
) -> None:
    """Generate a PDF marking differences between two revisions."""
    with fitz.open(old_pdf) as doc_old, fitz.open(new_pdf) as doc_new, fitz.open() as out:
        max_pages = max(len(doc_old), len(doc_new))
        for i in range(max_pages):
            base = doc_old[i] if i < len(doc_old) else doc_new[i]
            page = out.new_page(width=base.rect.width, height=base.rect.height)
            if i < len(doc_old):
                page.show_pdf_page(page.rect, doc_old, i)
            if i < len(doc_new):
                page.show_pdf_page(page.rect, doc_new, i, overlay=True)
            for diff, color in ((removed, color_remove), (added, color_add)):
                for item in diff:
                    if item["page"] != i:
                        continue
                    r = fitz.Rect(item["bbox"])
                    page.draw_rect(r, color=color, fill_opacity=0.3, width=0.5)
        out.save(output_pdf)
