"""Vector-based PDF comparison highlighting changed paths.

This module provides :func:`compare_pdfs` which compares two PDFs and
highlights vector differences by altering the color of modified paths.
The implementation relies on ``PyMuPDF`` and does not draw rectangles or
annotations over the documents.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple
import logging

import fitz  # type: ignore

from compareset.utils import normalize_pdf_to_reference

logger = logging.getLogger(__name__)

COLOR_REMOVE_DEFAULT: Tuple[float, float, float] = (1, 0, 0)
COLOR_ADD_DEFAULT: Tuple[float, float, float] = (0, 0.8, 0)


@dataclass
class Vector:
    """Information about a drawing object."""

    items: List[Tuple]
    rect: fitz.Rect
    width: float
    stroke: Tuple[float, float, float] | None
    fill: Tuple[float, float, float] | None
    even_odd: bool


# ---------------------------------------------------------------------------
# Vector utilities
# ---------------------------------------------------------------------------

def _extract_vectors(page: fitz.Page) -> List[Vector]:
    """Return drawing commands from ``page`` as :class:`Vector` objects."""

    vectors: List[Vector] = []
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
        else:
            r = fitz.Rect(0, 0, 0, 0)
        width_val = drawing.get("width")
        width = float(width_val) if width_val is not None else 1.0
        vectors.append(
            Vector(
                items=list(drawing.get("items", [])),
                rect=r,
                width=width,
                stroke=drawing.get("color"),
                fill=drawing.get("fill"),
                even_odd=bool(drawing.get("even_odd", False)),
            )
        )
    return vectors


def _param_to_list(value: object) -> List[float]:
    """Return ``value`` as a flat list of floats."""

    if isinstance(value, fitz.Point):
        return [float(value.x), float(value.y)]
    if isinstance(value, fitz.Rect):
        return [
            float(value.x0),
            float(value.y0),
            float(value.x1),
            float(value.y1),
        ]
    if hasattr(fitz, "Quad") and isinstance(value, fitz.Quad):
        vals: List[float] = []
        for pt in value:
            vals.extend(_param_to_list(pt))
        return vals
    if isinstance(value, (list, tuple)):
        vals: List[float] = []
        for v in value:
            vals.extend(_param_to_list(v))
        return vals
    return [float(value)]


def _vectors_equal(a: Vector, b: Vector, eps: float = 0.1) -> bool:
    """Return ``True`` when two vectors are considered equal."""

    if len(a.items) != len(b.items):
        return False
    for it_a, it_b in zip(a.items, b.items):
        if it_a[0] != it_b[0] or len(it_a) != len(it_b):
            return False
        for pa, pb in zip(it_a[1:], it_b[1:]):
            list_a = _param_to_list(pa)
            list_b = _param_to_list(pb)
            if len(list_a) != len(list_b):
                return False
            for xa, xb in zip(list_a, list_b):
                if abs(xa - xb) > eps:
                    return False
    return True


def _compare_vectors(
    old: List[Vector], new: List[Vector], eps: float = 0.1
) -> Tuple[List[Vector], List[Vector]]:
    """Return removed and added vectors between two lists."""

    removed: List[Vector] = []
    added: List[Vector] = []
    matched = set()

    for ov in old:
        found = None
        for idx, nv in enumerate(new):
            if idx in matched:
                continue
            if _vectors_equal(ov, nv, eps):
                found = idx
                break
        if found is None:
            removed.append(ov)
        else:
            matched.add(found)

    added.extend(nv for idx, nv in enumerate(new) if idx not in matched)
    return removed, added


def _draw_vector(page: fitz.Page, vec: Vector, color: Tuple[float, float, float]):
    """Draw ``vec`` on ``page`` with stroke color ``color``."""

    # ``fitz.Path`` was introduced in more recent versions of PyMuPDF. Older
    # releases only provide drawing capabilities via the :class:`Shape` API.
    use_path = hasattr(fitz, "Path") and hasattr(page, "draw_path")

    if use_path:
        path = fitz.Path()
        move_to = path.move_to
        line_to = path.line_to
        curve_to = path.curve_to
        rect = path.rect
        close_path = path.close_path
    else:  # fallback for old PyMuPDF versions
        shape = page.new_shape()
        # method names changed from camelCase to snake_case in PyMuPDF
        move_to = getattr(shape, "move_to", None) or getattr(shape, "moveTo", None)
        line_to = getattr(shape, "line_to", None) or getattr(shape, "lineTo", None)
        curve_to = getattr(shape, "curve_to", None) or getattr(shape, "curveTo", None)
        rect = getattr(shape, "draw_rect", None) or getattr(shape, "drawRect", None)
        close_path = getattr(shape, "close_path", None) or getattr(shape, "closePath", None)

    for item in vec.items:
        op = item[0]
        args = item[1:]
        if op == "m":
            move_to(args[0], args[1])
        elif op == "l":
            line_to(args[0], args[1])
        elif op == "c":
            curve_to(args[0], args[1], args[2], args[3], args[4], args[5])
        elif op == "re":
            r = fitz.Rect(args)
            rect(r.x0, r.y0, r.x1, r.y1)
        elif op == "h":
            close_path()
        # unsupported commands are ignored

    if use_path:
        page.draw_path(
            path,
            color=color if vec.width > 0 else None,
            fill=color if vec.fill else None,
            width=vec.width,
            even_odd=vec.even_odd,
        )
    else:
        shape.finish(
            color=color if vec.width > 0 else None,
            fill=color if vec.fill else None,
            width=vec.width,
            rule=1 if vec.even_odd else 0,
        )
        shape.commit()


# ---------------------------------------------------------------------------
# Main comparison logic
# ---------------------------------------------------------------------------

def compare_pdfs(
    pdf_old: str,
    pdf_new: str,
    *,
    mode: str = "overlay",
    color_add: Tuple[float, float, float] = COLOR_ADD_DEFAULT,
    color_remove: Tuple[float, float, float] = COLOR_REMOVE_DEFAULT,
    debug: bool | None = None,
    output_path: str = "output.pdf",
) -> None:
    """Compare two PDFs and generate ``output_path``.

    The result contains either overlay pages or split pages depending on
    ``mode``. Vector differences are highlighted by drawing modified
    paths again with ``color_add`` or ``color_remove``.
    """

    if mode not in {"overlay", "split"}:
        raise ValueError("mode must be 'overlay' or 'split'")

    with fitz.open(pdf_old) as doc_old, fitz.open() as final:
        normalized = normalize_pdf_to_reference(pdf_old, pdf_new)
        doc_new = normalized.document
        try:
            max_pages = max(len(doc_old), len(doc_new))
            for i in range(max_pages):
                old_page = doc_old[i] if i < len(doc_old) else None
                new_page = doc_new[i] if i < len(doc_new) else None

                old_vecs = _extract_vectors(old_page) if old_page else []
                new_vecs = _extract_vectors(new_page) if new_page else []
                removed, added = _compare_vectors(old_vecs, new_vecs)

                if debug:
                    logger.debug(
                        "page %d: %d removed, %d added", i, len(removed), len(added)
                    )

                if mode == "overlay":
                    base = old_page if old_page else new_page
                    page_out = final.new_page(
                        width=base.rect.width, height=base.rect.height
                    )
                    if old_page:
                        page_out.show_pdf_page(page_out.rect, doc_old, i)
                    if new_page:
                        page_out.show_pdf_page(page_out.rect, doc_new, i, overlay=True)
                    for vec in removed:
                        _draw_vector(page_out, vec, color_remove)
                    for vec in added:
                        _draw_vector(page_out, vec, color_add)
                else:  # split
                    if old_page:
                        page_rem = final.new_page(
                            width=old_page.rect.width, height=old_page.rect.height
                        )
                        page_rem.show_pdf_page(page_rem.rect, doc_old, i)
                        for vec in removed:
                            _draw_vector(page_rem, vec, color_remove)
                    if new_page:
                        page_add = final.new_page(
                            width=new_page.rect.width, height=new_page.rect.height
                        )
                        page_add.show_pdf_page(page_add.rect, doc_new, i)
                        for vec in added:
                            _draw_vector(page_add, vec, color_add)
            final.save(output_path)
            logger.info("comparison saved to %s", output_path)
        finally:
            doc_new.close()


def gerar_pdf_com_destaques(
    pdf_old: str,
    pdf_new: str,
    removidos: list | None = None,
    adicionados: list | None = None,
    output_pdf: str = "output.pdf",
    color_add: Tuple[float, float, float] = COLOR_ADD_DEFAULT,
    color_remove: Tuple[float, float, float] = COLOR_REMOVE_DEFAULT,
    overlay: bool = True,
) -> None:
    """Compatibility wrapper for the old API."""

    logger.warning("gerar_pdf_com_destaques is deprecated; use compare_pdfs")
    mode = "overlay" if overlay else "split"
    compare_pdfs(
        pdf_old,
        pdf_new,
        mode=mode,
        color_add=color_add,
        color_remove=color_remove,
        output_path=output_pdf,
    )
