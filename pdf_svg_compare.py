"""Hybrid SVG-based PDF comparison using PyMuPDF for detection."""

from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple

import fitz  # type: ignore

logger = logging.getLogger(__name__)


Rect = Tuple[float, float, float, float]


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


def _extract_page_elements(page: fitz.Page) -> List[Rect]:
    """Return bounding boxes of drawings, images and text blocks."""
    boxes: List[Rect] = []

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

    for img in page.get_images(full=True):
        xref = img[0]
        for r in page.get_image_rects(xref):
            rect = r if isinstance(r, fitz.Rect) else fitz.Rect(r)
            boxes.append((float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)))

    for block in page.get_text("blocks"):
        if len(block) >= 4:
            r = fitz.Rect(block[:4])
            boxes.append((float(r.x0), float(r.y0), float(r.x1), float(r.y1)))

    return boxes


def _compare_elements(old: List[Rect], new: List[Rect], thr: float = 0.9) -> Tuple[List[Rect], List[Rect]]:
    """Return removed and added bounding boxes based on IoU."""
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


def compare_pdfs(pdf_old: str, pdf_new: str) -> Dict[int, Dict[str, List[Rect]]]:
    """Compare two PDFs and return bounding boxes of differences."""
    result: Dict[int, Dict[str, List[Rect]]] = {}
    with fitz.open(pdf_old) as doc_old, fitz.open(pdf_new) as doc_new:
        max_pages = max(len(doc_old), len(doc_new))
        for i in range(max_pages):
            old_page = doc_old[i] if i < len(doc_old) else None
            new_page = doc_new[i] if i < len(doc_new) else None

            old_boxes = _extract_page_elements(old_page) if old_page else []
            new_boxes = _extract_page_elements(new_page) if new_page else []
            removed, added = _compare_elements(old_boxes, new_boxes)
            result[i] = {"removed": removed, "added": added}

            total = len(old_boxes) + len(new_boxes)
            logger.info(
                "page %d: compared %d elements, %d removed, %d added",
                i,
                total,
                len(removed),
                len(added),
            )

    json_ready = {
        p: {
            "removed": [list(r) for r in data["removed"]],
            "added": [list(a) for a in data["added"]],
        }
        for p, data in result.items()
    }
    with open("differences.json", "w", encoding="utf-8") as fh:
        json.dump(json_ready, fh, indent=2)
    return result


# ---------------------------------------------------------------------------
# SVG utilities
# ---------------------------------------------------------------------------

def export_svgs(pdf_path: str, prefix: str) -> List[str]:
    """Export each page of ``pdf_path`` to an SVG file."""
    paths: List[str] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            svg = page.get_svg_image()
            out = f"{prefix}_page_{i+1}.svg"
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(svg)
            paths.append(out)
    return paths


def _element_bbox(el: ET.Element) -> Tuple[float, float, float, float] | None:
    tag = el.tag.split("}")[-1]
    try:
        if tag == "rect":
            x = float(el.get("x", "0"))
            y = float(el.get("y", "0"))
            w = float(el.get("width", "0"))
            h = float(el.get("height", "0"))
            return (x, y, x + w, y + h)
        if tag == "line":
            x1 = float(el.get("x1", "0"))
            y1 = float(el.get("y1", "0"))
            x2 = float(el.get("x2", "0"))
            y2 = float(el.get("y2", "0"))
            return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        if tag in {"polyline", "polygon"}:
            pts = re.findall(r"-?\d+(?:\.\d+)?", el.get("points", ""))
            xs = list(map(float, pts[0::2]))
            ys = list(map(float, pts[1::2]))
            if xs and ys:
                return (min(xs), min(ys), max(xs), max(ys))
        if tag == "path":
            nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", el.get("d", ""))]
            xs = nums[0::2]
            ys = nums[1::2]
            if xs and ys:
                return (min(xs), min(ys), max(xs), max(ys))
    except Exception:  # pragma: no cover - best effort
        return None
    return None


def _style_set(color: str, el: ET.Element) -> None:
    style = el.get("style")
    if style:
        parts = {}
        for item in style.split(";"):
            if ":" in item:
                k, v = item.split(":", 1)
                parts[k.strip()] = v.strip()
        if "stroke" in parts:
            parts["stroke"] = color
        if "fill" in parts and parts["fill"] != "none":
            parts["fill"] = color
        el.set("style", ";".join(f"{k}:{v}" for k, v in parts.items()))
    else:
        if el.get("stroke") is not None:
            el.set("stroke", color)
        if el.get("fill") not in (None, "none"):
            el.set("fill", color)


def recolor_svg(svg_path: str, diffs: List[Rect], color: str, output_path: str) -> None:
    """Recolor SVG elements intersecting any ``diffs`` rectangles."""
    tree = ET.parse(svg_path)
    root = tree.getroot()
    diff_rects = [fitz.Rect(r) for r in diffs]

    for el in root.iter():
        bbox = _element_bbox(el)
        if bbox is None:
            continue
        r = fitz.Rect(bbox)
        if any(r.intersects(d) for d in diff_rects):
            _style_set(color, el)

    tree.write(output_path)


def generate_recolored_svgs(
    pdf_old: str,
    pdf_new: str,
    *,
    color_add: str = "rgb(0,255,0)",
    color_remove: str = "rgb(255,0,0)",
    prefix_old: str = "old_color",
    prefix_new: str = "new_color",
) -> Tuple[List[str], List[str]]:
    """Return recolored SVG pages for ``pdf_old`` and ``pdf_new``."""
    logger.info("Comparing PDFs %s vs %s", pdf_old, pdf_new)
    diffs = compare_pdfs(pdf_old, pdf_new)
    logger.info("Exporting SVGs")
    old_svgs = export_svgs(pdf_old, "old")
    new_svgs = export_svgs(pdf_new, "new")
    recolored_old: List[str] = []
    recolored_new: List[str] = []
    logger.info("Recoloring old document SVGs")
    for i, path in enumerate(old_svgs):
        out = f"{prefix_old}_{i+1}.svg"
        diff_rects = diffs.get(i, {}).get("removed", [])
        recolor_svg(path, diff_rects, color_remove, out)
        recolored_old.append(out)
    logger.info("Recoloring new document SVGs")
    for i, path in enumerate(new_svgs):
        out = f"{prefix_new}_{i+1}.svg"
        diff_rects = diffs.get(i, {}).get("added", [])
        recolor_svg(path, diff_rects, color_add, out)
        recolored_new.append(out)
    return recolored_old, recolored_new


# ---------------------------------------------------------------------------
# SVG to PDF and final composition
# ---------------------------------------------------------------------------

def _svg_to_pdf(svg_path: str, pdf_path: str) -> None:
    try:
        import cairosvg  # type: ignore
    except Exception as exc:  # pragma: no cover - runtime only
        raise RuntimeError("cairosvg required to export PDF") from exc
    cairosvg.svg2pdf(url=svg_path, write_to=pdf_path)


def generate_colored_comparison(
    pdf_old: str,
    pdf_new: str,
    mode: str = "overlay",
    *,
    color_add: str = "rgb(0,255,0)",
    color_remove: str = "rgb(255,0,0)",
    output_path: str = "comparison.pdf",
) -> None:
    """Generate a colored comparison PDF based on SVG recoloring."""
    if mode not in {"overlay", "split"}:
        raise ValueError("mode must be 'overlay' or 'split'")

    recolored_old, recolored_new = generate_recolored_svgs(
        pdf_old,
        pdf_new,
        color_add=color_add,
        color_remove=color_remove,
    )

    old_pdfs = []
    new_pdfs = []
    for i, svg in enumerate(recolored_old):
        pdf = f"old_{i+1}.pdf"
        _svg_to_pdf(svg, pdf)
        old_pdfs.append(pdf)
    for i, svg in enumerate(recolored_new):
        pdf = f"new_{i+1}.pdf"
        _svg_to_pdf(svg, pdf)
        new_pdfs.append(pdf)

    final = fitz.open()
    max_pages = max(len(old_pdfs), len(new_pdfs))
    for i in range(max_pages):
        old_pdf = fitz.open(old_pdfs[i]) if i < len(old_pdfs) else None
        new_pdf = fitz.open(new_pdfs[i]) if i < len(new_pdfs) else None
        try:
            if mode == "overlay":
                base = old_pdf or new_pdf
                assert base is not None
                page_out = final.new_page(width=base[0].rect.width, height=base[0].rect.height)
                if old_pdf:
                    page_out.show_pdf_page(page_out.rect, old_pdf, 0)
                if new_pdf:
                    page_out.show_pdf_page(page_out.rect, new_pdf, 0, overlay=True)
            else:
                if old_pdf:
                    page = final.new_page(width=old_pdf[0].rect.width, height=old_pdf[0].rect.height)
                    page.show_pdf_page(page.rect, old_pdf, 0)
                if new_pdf:
                    page = final.new_page(width=new_pdf[0].rect.width, height=new_pdf[0].rect.height)
                    page.show_pdf_page(page.rect, new_pdf, 0)
        finally:
            if old_pdf:
                old_pdf.close()
            if new_pdf:
                new_pdf.close()

    final.save(output_path)
    final.close()
    logger.info("colored comparison saved to %s", output_path)
