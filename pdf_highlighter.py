"""PDF comparison and highlighting utilities."""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Tuple, Any

import fitz  # type: ignore

from compareset.utils.normalize import normalize_pdf_to_reference


logger = logging.getLogger(__name__)

Rect = Tuple[float, float, float, float]
Diff = Dict[str, Any]


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _iou(a: Rect, b: Rect) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter = inter_w * inter_h
    if inter == 0.0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def _parse_color(value: str) -> Tuple[float, float, float]:
    """Return a ``fitz`` compatible color tuple from ``value``."""
    if value.startswith("rgb("):
        nums = [float(n) for n in re.findall(r"\d+", value)]
        r, g, b = nums[:3]
    elif value.startswith("#") and len(value) >= 7:
        r = int(value[1:3], 16)
        g = int(value[3:5], 16)
        b = int(value[5:7], 16)
    else:  # pragma: no cover - fallback for unexpected formats
        raise ValueError(f"Invalid color: {value}")
    return (r / 255.0, g / 255.0, b / 255.0)


def _extract_text(page: fitz.Page | None) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    if page is None:
        return blocks
    for block in page.get_text("blocks"):
        if len(block) >= 5:
            rect = fitz.Rect(block[:4])
            text = block[4].strip()
            blocks.append(
                {
                    "bbox": (
                        float(rect.x0),
                        float(rect.y0),
                        float(rect.x1),
                        float(rect.y1),
                    ),
                    "text": text,
                }
            )
    return blocks


def _extract_vectors(page: fitz.Page | None) -> List[Rect]:
    boxes: List[Rect] = []
    if page is None:
        return boxes
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if not rect:
            xs: List[float] = []
            ys: List[float] = []
            for item in drawing.get("items", []):
                for pt in item[1:]:
                    if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                        xs.append(float(pt[0]))
                        ys.append(float(pt[1]))
            if xs and ys:
                rect = fitz.Rect(min(xs), min(ys), max(xs), max(ys))
        if rect:
            r = rect if isinstance(rect, fitz.Rect) else fitz.Rect(rect)
            boxes.append((float(r.x0), float(r.y0), float(r.x1), float(r.y1)))
    return boxes


def _compare_text_blocks(
    old: List[Dict[str, Any]], new: List[Dict[str, Any]], thr: float
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    removed: List[Dict[str, Any]] = []
    added: List[Dict[str, Any]] = []
    matched = set()
    for ob in old:
        found = None
        for idx, nb in enumerate(new):
            if idx in matched:
                continue
            if ob["text"] == nb["text"] and _iou(ob["bbox"], nb["bbox"]) >= thr:
                found = idx
                break
        if found is None:
            removed.append(ob)
        else:
            matched.add(found)
    added.extend(nb for idx, nb in enumerate(new) if idx not in matched)
    return removed, added


def _compare_boxes(
    old: List[Rect], new: List[Rect], thr: float
) -> Tuple[List[Rect], List[Rect]]:
    removed: List[Rect] = []
    added: List[Rect] = []
    matched = set()
    for ob in old:
        found = None
        for idx, nb in enumerate(new):
            if idx in matched:
                continue
            if _iou(ob, nb) >= thr:
                found = idx
                break
        if found is None:
            removed.append(ob)
        else:
            matched.add(found)
    added.extend(nb for idx, nb in enumerate(new) if idx not in matched)
    return removed, added


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compare_pdfs(
    pdf_old: str,
    pdf_new: str,
    *,
    iou_threshold: float = 0.6,
    compare_text: bool = True,
    compare_geom: bool = True,
) -> Tuple[Dict[int, List[Diff]], fitz.Document]:
    """Compare two PDFs and return differences and normalized new document."""
    normalized = normalize_pdf_to_reference(pdf_old, pdf_new)
    diffs: Dict[int, List[Diff]] = {}
    with fitz.open(pdf_old) as doc_old:
        doc_new = normalized.document
        max_pages = max(len(doc_old), len(doc_new))
        for i in range(max_pages):
            old_page = doc_old[i] if i < len(doc_old) else None
            new_page = doc_new[i] if i < len(doc_new) else None
            page_diffs: List[Diff] = []
            old_text: List[Dict[str, Any]] = []
            new_text: List[Dict[str, Any]] = []
            old_vec: List[Rect] = []
            new_vec: List[Rect] = []
            if compare_text:
                old_text = _extract_text(old_page)
                new_text = _extract_text(new_page)
                rem_t, add_t = _compare_text_blocks(old_text, new_text, iou_threshold)
                for r in rem_t:
                    page_diffs.append(
                        {"bbox": r["bbox"], "type": "text", "status": "removed"}
                    )
                for a in add_t:
                    page_diffs.append(
                        {"bbox": a["bbox"], "type": "text", "status": "added"}
                    )
            if compare_geom:
                old_vec = _extract_vectors(old_page)
                new_vec = _extract_vectors(new_page)
                rem_g, add_g = _compare_boxes(old_vec, new_vec, iou_threshold)
                for r in rem_g:
                    page_diffs.append({"bbox": r, "type": "geom", "status": "removed"})
                for a in add_g:
                    page_diffs.append({"bbox": a, "type": "geom", "status": "added"})
            diffs[i] = page_diffs
            logger.info(
                "Page %d: %d vectors compared, %d removed, %d added.",
                i,
                len(old_vec) + len(new_vec),
                len(
                    [
                        d
                        for d in page_diffs
                        if d["type"] == "geom" and d["status"] == "removed"
                    ]
                ),
                len(
                    [
                        d
                        for d in page_diffs
                        if d["type"] == "geom" and d["status"] == "added"
                    ]
                ),
            )
            logger.info(
                "Page %d: %d text blocks compared, %d removed, %d added.",
                i,
                len(old_text) + len(new_text),
                len(
                    [
                        d
                        for d in page_diffs
                        if d["type"] == "text" and d["status"] == "removed"
                    ]
                ),
                len(
                    [
                        d
                        for d in page_diffs
                        if d["type"] == "text" and d["status"] == "added"
                    ]
                ),
            )
    return diffs, normalized.document


def _highlight_differences(
    doc_old: fitz.Document,
    doc_new: fitz.Document,
    diffs: Dict[int, List[Diff]],
    *,
    mode: str,
    color_add: str,
    color_remove: str,
) -> fitz.Document:
    """Return a document with ``diffs`` highlighted."""
    col_add = _parse_color(color_add)
    col_rem = _parse_color(color_remove)
    final = fitz.open()
    max_pages = max(len(doc_old), len(doc_new))
    for i in range(max_pages):
        old_page = doc_old[i] if i < len(doc_old) else None
        new_page = doc_new[i] if i < len(doc_new) else None
        if mode == "overlay":
            base = old_page or new_page
            if base is None:
                continue
            out = final.new_page(width=base.rect.width, height=base.rect.height)
            if old_page:
                out.show_pdf_page(out.rect, doc_old, i)
            if new_page:
                out.show_pdf_page(out.rect, doc_new, i, overlay=True)
            _apply_page_highlights(out, diffs.get(i, []), col_add, col_rem)
        else:  # split
            if old_page:
                out = final.new_page(
                    width=old_page.rect.width, height=old_page.rect.height
                )
                out.show_pdf_page(out.rect, doc_old, i)
                _apply_page_highlights(
                    out,
                    [d for d in diffs.get(i, []) if d["status"] == "removed"],
                    col_add,
                    col_rem,
                )
            if new_page:
                out = final.new_page(
                    width=new_page.rect.width, height=new_page.rect.height
                )
                out.show_pdf_page(out.rect, doc_new, i)
                _apply_page_highlights(
                    out,
                    [d for d in diffs.get(i, []) if d["status"] == "added"],
                    col_add,
                    col_rem,
                )
    return final


def _apply_page_highlights(
    page: fitz.Page,
    diffs: List[Diff],
    col_add: Tuple[float, float, float],
    col_rem: Tuple[float, float, float],
) -> None:
    for diff in diffs:
        rect = fitz.Rect(diff["bbox"])
        color = col_add if diff["status"] == "added" else col_rem
        if diff["type"] == "text":
            annot = page.add_highlight_annot(rect)
            annot.set_colors(stroke=color, fill=color)
            annot.update()
        else:
            shape = page.new_shape()
            shape.draw_rect(rect)
            shape.finish(color=color, width=1)
            shape.commit()
        logger.debug(
            "Page %d: highlighted %s %s", page.number, diff["status"], diff["type"]
        )


# ---------------------------------------------------------------------------
# High-level interface
# ---------------------------------------------------------------------------


def generate_colored_comparison(
    pdf_old: str,
    pdf_new: str,
    mode: str = "overlay",
    *,
    color_add: str = "rgb(0,255,0)",
    color_remove: str = "rgb(255,0,0)",
    output_path: str = "comparison.pdf",
    iou_threshold: float = 0.6,
    compare_text: bool = True,
    compare_geom: bool = True,
) -> None:
    """Generate a comparison PDF with highlights."""
    diffs, norm_doc = compare_pdfs(
        pdf_old,
        pdf_new,
        iou_threshold=iou_threshold,
        compare_text=compare_text,
        compare_geom=compare_geom,
    )
    with fitz.open(pdf_old) as doc_old:
        doc_new = norm_doc
        final = _highlight_differences(
            doc_old,
            doc_new,
            diffs,
            mode=mode,
            color_add=color_add,
            color_remove=color_remove,
        )
        final.save(output_path)
        final.close()
        doc_new.close()
    logger.info("colored comparison saved to %s", output_path)


def export_svgs(
    pdf_path: str, prefix: str
) -> List[str]:  # pragma: no cover - optional helper
    paths: List[str] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            svg = page.get_svg_image()
            out = f"{prefix}_page_{i+1}.svg"
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(svg)
            paths.append(out)
    return paths
