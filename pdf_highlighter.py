"""PDF comparison highlighting vector changes by color modification."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import fitz  # PyMuPDF

from compareset.utils import normalize_pdf_to_reference
from pdf_diff import CancelledError, InvalidDimensionsError

logger = logging.getLogger(__name__)

Color = Tuple[float, float, float]

COLOR_REMOVE_DEFAULT: Color = (1.0, 0.0, 0.0)
COLOR_ADD_DEFAULT: Color = (0.0, 0.8, 0.0)


@dataclass(frozen=True)
class Vector:
    """Representation of a vector path."""

    geometry: Tuple
    stroke: Optional[Color]
    fill: Optional[Color]


def _extract_vectors(page: fitz.Page) -> List[Vector]:
    """Return a simplified list of vector paths for ``page``."""
    vectors: List[Vector] = []
    for drawing in page.get_drawings():
        geom: List[Tuple] = []
        for item in drawing.get("items", []):
            op = item[0]
            coords = tuple(round(float(v), 2) for v in item[1:])
            geom.append((op, coords))
        vectors.append(
            Vector(
                geometry=tuple(geom),
                stroke=drawing.get("color"),
                fill=drawing.get("fill"),
            )
        )
    return vectors


def _diff_vectors(
    old: Iterable[Vector], new: Iterable[Vector]
) -> Tuple[List[Vector], List[Vector]]:
    """Return removed and added vectors comparing ``old`` and ``new``."""

    def _key(v: Vector) -> Tuple:
        return v.geometry

    old_map: Dict[Tuple, Vector] = {_key(v): v for v in old}
    new_map: Dict[Tuple, Vector] = {_key(v): v for v in new}

    removed = []
    added = []

    for k, ov in old_map.items():
        nv = new_map.get(k)
        if nv is None or ov.stroke != nv.stroke or ov.fill != nv.fill:
            removed.append(ov)
    for k, nv in new_map.items():
        ov = old_map.get(k)
        if ov is None or ov.stroke != nv.stroke or ov.fill != nv.fill:
            added.append(nv)
    return removed, added


def _rebuild_page(
    src_page: fitz.Page,
    dest_doc: fitz.Document,
    vectors_old: List[Vector],
    vectors_new: List[Vector],
    color_add: Color,
    color_remove: Color,
    mode: str,
) -> None:
    """Rebuild ``src_page`` in ``dest_doc`` applying color changes."""
    # NOTE: PyMuPDF does not provide direct APIs to modify vector colors in
    # place.  This function rebuilds the page by replaying its drawing commands
    # with updated colors.  Text and images are copied verbatim.
    dest_page = dest_doc.new_page(
        width=src_page.rect.width, height=src_page.rect.height
    )

    textpage = src_page.get_textpage()
    dest_page.show_pdf_page(dest_page.rect, src_page.parent, src_page.number)

    removed, added = _diff_vectors(vectors_old, vectors_new)

    shape = dest_page.new_shape()
    for vec in vectors_new:
        stroke = vec.stroke
        fill = vec.fill
        if vec in added:
            stroke = color_add if stroke is not None else None
            fill = color_add if fill is not None else None
        elif vec in removed and mode == "overlay":
            stroke = color_remove if stroke is not None else None
            fill = color_remove if fill is not None else None
        shape.draw_path(vec.geometry, stroke=stroke, fill=fill)
    if mode == "overlay":
        for vec in removed:
            if vec in vectors_new:
                continue
            shape.draw_path(vec.geometry, stroke=color_remove, fill=color_remove)
    shape.commit()


def compare_pdfs(
    pdf_old: str,
    pdf_new: str,
    output_pdf: str,
    mode: str = "overlay",
    *,
    color_add: Color = COLOR_ADD_DEFAULT,
    color_remove: Color = COLOR_REMOVE_DEFAULT,
    progress_callback: Optional[Callable[[float], None]] = None,
    cancel_callback: Optional[Callable[[], bool]] = None,
) -> None:
    """Compare two PDFs and highlight vector changes by recoloring them."""
    if mode not in {"overlay", "split"}:
        raise ValueError("mode must be 'overlay' or 'split'")

    with fitz.open(pdf_old) as doc_old, fitz.open() as result:
        normalized = normalize_pdf_to_reference(pdf_old, pdf_new)
        doc_new = normalized.document
        try:
            max_pages = max(len(doc_old), len(doc_new))
            for i in range(max_pages):
                if cancel_callback and cancel_callback():
                    raise CancelledError()
                old_page = doc_old[i] if i < len(doc_old) else None
                new_page = doc_new[i] if i < len(doc_new) else None
                base = new_page or old_page
                if base is None:
                    continue
                if base.rect.width == 0 or base.rect.height == 0:
                    raise InvalidDimensionsError(
                        f"page {i} has invalid size ({base.rect.width} x {base.rect.height})"
                    )
                old_vec = _extract_vectors(old_page) if old_page else []
                new_vec = _extract_vectors(new_page) if new_page else []

                if mode == "overlay":
                    _rebuild_page(
                        base,
                        result,
                        old_vec,
                        new_vec,
                        color_add,
                        color_remove,
                        mode,
                    )
                else:  # split
                    if old_page is not None:
                        _rebuild_page(
                            old_page,
                            result,
                            old_vec,
                            [],
                            color_add,
                            color_remove,
                            mode,
                        )
                    if new_page is not None:
                        _rebuild_page(
                            new_page,
                            result,
                            [],
                            new_vec,
                            color_add,
                            color_remove,
                            mode,
                        )
                if progress_callback:
                    progress_callback((i + 1) / max_pages * 100)
            result.save(output_pdf)
        finally:
            doc_new.close()


# compatibility wrapper


def gerar_pdf_com_destaques(
    pdf_old: str,
    pdf_new: str,
    removidos: List[dict],  # unused
    adicionados: List[dict],  # unused
    output_pdf: str,
    color_add: Color = COLOR_ADD_DEFAULT,
    color_remove: Color = COLOR_REMOVE_DEFAULT,
    overlay: bool = True,
    progress_callback: Optional[Callable[[float], None]] = None,
    cancel_callback: Optional[Callable[[], bool]] = None,
) -> None:
    """Backward compatible wrapper around :func:`compare_pdfs`."""

    compare_pdfs(
        pdf_old,
        pdf_new,
        output_pdf,
        mode="overlay" if overlay else "split",
        color_add=color_add,
        color_remove=color_remove,
        progress_callback=progress_callback,
        cancel_callback=cancel_callback,
    )
