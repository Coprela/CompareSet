from __future__ import annotations

"""Utilities for comparing PDF documents."""

from typing import Callable, Dict, List, Optional, Sequence, Tuple

import logging

import fitz
from compareset.utils import normalize_pdf_to_reference

logger = logging.getLogger(__name__)

try:
    version_str = fitz.__doc__.split()[1]
except Exception:
    version_str = getattr(fitz, "__version__", "0")
version_tuple = tuple(int(p) for p in version_str.split(".")[:2])
if version_tuple < (1, 22):
    raise RuntimeError("PyMuPDF >=1.22 required")

# common ISO sizes in millimetres (width, height)
STANDARD_PAGE_SIZES_MM = {
    "A0": (841, 1189),
    "A1": (594, 841),
    "A2": (420, 594),
    "A3": (297, 420),
    "A4": (210, 297),
    "A5": (148, 210),
    "A6": (105, 148),
    "A7": (74, 105),
}


def _get_standard_label(width_pt: float, height_pt: float, tol_mm: float = 2) -> str:
    """Return the ISO size label for a page or an empty string."""
    mm_per_pt = 25.4 / 72
    w_mm = width_pt * mm_per_pt
    h_mm = height_pt * mm_per_pt
    for label, (w, h) in STANDARD_PAGE_SIZES_MM.items():
        if abs(w_mm - w) <= tol_mm and abs(h_mm - h) <= tol_mm:
            return label
        if abs(w_mm - h) <= tol_mm and abs(h_mm - w) <= tol_mm:
            return label
    return ""


class CancelledError(Exception):
    """Raised when a comparison operation is cancelled."""

    pass


class InvalidDimensionsError(Exception):
    """Raised when PDF pages have invalid sizes."""

    pass


def _extract_bboxes(
    doc: fitz.Document,
    transforms: Optional[List[Sequence[float]]] = None,
    ignore_geometry: bool = False,
    ignore_text: bool = False,
) -> List[List[Tuple[float, float, float, float, str]]]:
    """Return list of bboxes per page from drawings and text blocks.

    Parameters
    ----------
    doc: fitz.Document
        Opened document whose pages will be processed.
    transforms: list of sequences(scale_x, scale_y, trans_x, trans_y[, rotation])
        or (a, b, c, d, e, f), optional
        Transformations applied to each page's coordinates. Each tuple must
        contain four, five or six numeric values. Rotation is given in degrees
        and defaults to ``0`` when omitted. When six values are supplied they
        are interpreted as the full transformation matrix ``(a, b, c, d, e, f)``
        accepted by :class:`fitz.Matrix` and used as-is.
    ignore_geometry: bool, optional
        When ``True`` skip drawing and image boxes, extracting only text.
    ignore_text: bool, optional
        When ``True`` skip text extraction, returning only drawing and image
        boxes.
    """
    pages: List[List[Tuple[float, float, float, float, str]]] = []
    if transforms is not None:
        for idx, t in enumerate(transforms):
            if not isinstance(t, (list, tuple)) or len(t) not in (4, 5, 6):
                raise ValueError(
                    "Transform %d must be a sequence of four, five or six numeric values"
                    % idx
                )
            for v in t:
                if not isinstance(v, (int, float)):
                    raise TypeError(
                        "Transform %d contains non-numeric value %r" % (idx, v)
                    )
    for i, page in enumerate(doc):
        tx = ty = 0.0
        matrix = None
        if transforms and i < len(transforms):
            t = transforms[i]
            if len(t) == 6:
                a, b, c, d, tx, ty = t
                if not (
                    a == 1 and b == 0 and c == 0 and d == 1 and tx == 0 and ty == 0
                ):
                    try:
                        matrix = fitz.Matrix(a, b, c, d, tx, ty)
                    except Exception as exc:
                        raise ValueError(
                            "Transform %d must contain 6 numeric values" % i
                        ) from exc
            elif len(t) in (4, 5):
                sx, sy, tx, ty = t[:4]
                rot = t[4] if len(t) == 5 else 0.0
                if sx != 1 or sy != 1 or rot:
                    try:
                        matrix = fitz.Matrix(sx, sy)
                    except Exception as exc:
                        raise ValueError(
                            "Transform %d must contain numeric scale values" % i
                        ) from exc
                    if rot:
                        matrix = matrix.preRotate(rot)
            else:
                raise ValueError(
                    "Transform %d must be a sequence of four, five or six numeric values"
                    % i
                )
        bboxes = []
        if not ignore_geometry:
            # Bounding boxes from drawing objects (no associated text)
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
                    if not isinstance(r, fitz.Rect):
                        r = fitz.Rect(r)
                    if matrix:
                        r = matrix * r
                    x0 = r.x0 + tx
                    y0 = r.y0 + ty
                    x1 = r.x1 + tx
                    y1 = r.y1 + ty
                    if x1 - x0 == 0:
                        x1 += 0.1
                    if y1 - y0 == 0:
                        y1 += 0.1
                    bboxes.append((x0, y0, x1, y1, ""))

            # Bounding boxes from images
            for img in page.get_images(full=True):
                xref = img[0]
                for r in page.get_image_rects(xref):
                    if not isinstance(r, fitz.Rect):
                        r = fitz.Rect(r)
                    r_t = matrix * r if matrix else r
                    bboxes.append(
                        (
                            r_t.x0 + tx,
                            r_t.y0 + ty,
                            r_t.x1 + tx,
                            r_t.y1 + ty,
                            "",
                        )
                    )

        # Bounding boxes from individual words instead of full text blocks
        if not ignore_text:
            for word in page.get_text("words"):
                if len(word) >= 5:
                    x0, y0, x1, y1, text = word[:5]
                    r = fitz.Rect(float(x0), float(y0), float(x1), float(y1))
                    if matrix:
                        r = matrix * r
                    bboxes.append(
                        (
                            r.x0 + tx,
                            r.y0 + ty,
                            r.x1 + tx,
                            r.y1 + ty,
                            str(text).strip(),
                        )
                    )

        pages.append(bboxes)
    return pages


def _iou(
    a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]
) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    inter_w = max(0, x2 - x1)
    inter_h = max(0, y2 - y1)
    inter = inter_w * inter_h
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def _load_pdf_without_signatures(path: str) -> fitz.Document:
    """Open a PDF removing digital signatures if present."""
    signed = False
    try:
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(4096)
                if not chunk:
                    break
                if b"/ByteRange" in chunk or b"/Type /Sig" in chunk:
                    signed = True
                    break
    except Exception as exc:  # pragma: no cover - runtime only
        logger.warning("Failed reading %s: %s", path, exc)

    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise RuntimeError(f"Failed to load PDF: {exc}") from exc

    if not signed:
        return doc

    cleaned = fitz.open()
    try:
        for i, page in enumerate(doc):
            new_page = cleaned.new_page(width=page.rect.width, height=page.rect.height)
            new_page.show_pdf_page(new_page.rect, doc, i)
        return cleaned
    except Exception as exc:
        doc.close()
        cleaned.close()
        raise RuntimeError(f"Failed to load signed PDF: {exc}") from exc
    finally:
        doc.close()

def _compare_page(
    old_boxes: List[Tuple[float, float, float, float, str]],
    new_boxes: List[Tuple[float, float, float, float, str]],
    thr: float,
) -> Tuple[
    List[Tuple[float, float, float, float, str]],
    List[Tuple[float, float, float, float, str]],
]:
    """Compare two lists of boxes returning removed and added ones."""
    matched_new = set()
    removed: List[Tuple[float, float, float, float, str]] = []
    added: List[Tuple[float, float, float, float, str]] = []

    for ob in old_boxes:
        found = False
        for i, nb in enumerate(new_boxes):
            if i in matched_new:
                continue
            if _iou(ob[:4], nb[:4]) >= thr:
                matched_new.add(i)
                found = True
                if ob[4].strip() != nb[4].strip():
                    # Geometry matches but text differs
                    removed.append(ob)
                    added.append(nb)
                break
        if not found:
            removed.append(ob)

    # Any new boxes not matched are considered additions
    added.extend(nb for i, nb in enumerate(new_boxes) if i not in matched_new)
    return removed, added


def _remove_unchanged(
    removidos: List[Dict],
    adicionados: List[Dict],
    eps: float = 0.01,
    iou_thr: float = 0.995,
) -> Tuple[List[Dict], List[Dict]]:
    """Filter out pairs of boxes that are effectively identical."""

    def _key(item: Dict) -> Tuple[int, Tuple[int, int, int, int]]:
        return (
            item["pagina"],
            tuple(int(round(v / eps)) for v in item["bbox"]),
        )

    rem_filtered: List[Dict] = []
    used_add = set()
    for r in removidos:
        key = _key(r)
        found = False
        for idx, a in enumerate(adicionados):
            if idx in used_add:
                continue
            if _key(a) == key or (
                r["pagina"] == a["pagina"]
                and r.get("texto", "").strip() == a.get("texto", "").strip()
                and _iou(tuple(r["bbox"]), tuple(a["bbox"])) >= iou_thr
            ):
                used_add.add(idx)
                found = True
                break
        if not found:
            rem_filtered.append(r)

    add_filtered = [a for i, a in enumerate(adicionados) if i not in used_add]
    return rem_filtered, add_filtered


def _remove_moved_same_text(
    removidos: List[Dict],
    adicionados: List[Dict],
    dist: float = 3.0,
    size_eps: float = 0.5,
    rel_size_eps: float = 0.1,
) -> Tuple[List[Dict], List[Dict]]:
    """Discard pairs with the same text that only moved slightly.

    Parameters
    ----------
    removidos, adicionados : list
        Lists of bounding boxes from :func:`comparar_pdfs`.
    dist : float, optional
        Maximum displacement in points for which moved elements are ignored.
    size_eps : float, optional
        Absolute tolerance for differences in width or height.
    rel_size_eps : float, optional
        Relative tolerance (as a fraction) for width or height changes.
    """

    def _center(b: List[float]) -> Tuple[float, float]:
        return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)

    filtered_rem: List[Dict] = []
    used_add = set()
    for r in removidos:
        match = None
        for i, a in enumerate(adicionados):
            if i in used_add or r["pagina"] != a["pagina"]:
                continue
            if r.get("texto", "").strip() == a.get("texto", "").strip():
                crx, cry = _center(r["bbox"])
                cax, cay = _center(a["bbox"])
                if abs(crx - cax) <= dist and abs(cry - cay) <= dist:
                    rw = r["bbox"][2] - r["bbox"][0]
                    rh = r["bbox"][3] - r["bbox"][1]
                    aw = a["bbox"][2] - a["bbox"][0]
                    ah = a["bbox"][3] - a["bbox"][1]
                    width_ok = abs(rw - aw) <= size_eps or abs(
                        rw - aw
                    ) <= rel_size_eps * max(rw, aw)
                    height_ok = abs(rh - ah) <= size_eps or abs(
                        rh - ah
                    ) <= rel_size_eps * max(rh, ah)
                    if width_ok and height_ok:
                        match = i
                        break
        if match is None:
            filtered_rem.append(r)
        else:
            used_add.add(match)

    filtered_add = [a for i, a in enumerate(adicionados) if i not in used_add]
    return filtered_rem, filtered_add


def comparar_pdfs(
    old_pdf: str,
    new_pdf: str,
    thr: float = 0.9,
    adaptive: bool = False,
    pos_tol: float = 3.0,
    ignore_geometry: bool = False,
    ignore_text: bool = False,
    progress_callback: Optional[Callable[[float], None]] = None,
    cancel_callback: Optional[Callable[[], bool]] = None,
) -> Dict[str, List[Dict]]:
    """Compare two PDFs and return removed and added bounding boxes.

    The function takes page dimensions into account. When pages have
    different sizes they are scaled and translated so that comparisons
    happen in a shared coordinate space based on the old PDF pages.

    Parameters
    ----------
    old_pdf, new_pdf : str
        Paths to the PDFs being compared.
    thr : float, optional
        Minimum IoU threshold used for matching elements between PDFs.
    adaptive : bool, optional
        When ``True`` the comparison is repeated decreasing the threshold from
        ``1.0`` down to ``thr`` in ``0.05`` steps. Iterations stop as soon as no
        new differences are found. This approach improves precision by
        progressively relaxing the tolerance.
    pos_tol : float, optional
        Maximum displacement in points allowed when elements move without
        altering their content. Boxes shifted less than this distance are
        ignored. Minor size variations (up to ``0.5`` points or roughly
        ``10%%``) are also skipped so that lines with negligible growth are
        not flagged as changes.
    ignore_geometry : bool, optional
        If ``True`` compare only text and numeric strings, ignoring drawing
        and image elements.
    ignore_text : bool, optional
        If ``True`` compare only drawing and image elements, ignoring words.
    progress_callback : callable, optional
        Function called with a ``0-100`` progress percentage.
    cancel_callback : callable, optional
        Function returning ``True`` to abort the operation.

    Returns
    -------
    dict
        Dictionary with keys ``removidos`` and ``adicionados`` listing the
        differences and ``verificados`` with the number of processed elements.
    """
    with _load_pdf_without_signatures(old_pdf) as doc_old, _load_pdf_without_signatures(
        new_pdf
    ) as doc_new:

        # warn when page dimensions are not standard ISO sizes
        for label, doc, name in [("old", doc_old, old_pdf), ("new", doc_new, new_pdf)]:
            warn_pages = [
                str(i + 1)
                for i, page in enumerate(doc)
                if not _get_standard_label(page.rect.width, page.rect.height)
            ]
            if warn_pages:
                pages = ", ".join(warn_pages)
                logger.warning(
                    "Warning: %s (%s) has non-standard page sizes on page(s): %s",
                    name,
                    label,
                    pages,
                )

        # normalize coordinates of the new PDF so they match the old one
        normalized = normalize_pdf_to_reference(old_pdf, new_pdf)
        doc_new_resized = normalized.document
        try:
            old_pages = _extract_bboxes(
                doc_old,
                ignore_geometry=ignore_geometry,
                ignore_text=ignore_text,
            )
            new_pages = _extract_bboxes(
                doc_new_resized,
                ignore_geometry=ignore_geometry,
                ignore_text=ignore_text,
            )
            max_pages = max(len(old_pages), len(new_pages))

            if adaptive:
                thr_values: List[float] = []
                val = 1.0
                while val >= thr:
                    thr_values.append(round(val, 2))
                    val -= 0.05
                if thr_values[-1] != thr:
                    thr_values.append(thr)
            else:
                thr_values = [thr]

            total_steps = max_pages * len(thr_values)
            result = {"removidos": [], "adicionados": [], "verificados": 0}
            elements_counted = False
            previous: Optional[Tuple[set, set]] = None

            for j, thr_val in enumerate(thr_values):
                removidos = []
                adicionados = []
                for page_num in range(max_pages):
                    old_boxes = old_pages[page_num] if page_num < len(old_pages) else []
                    new_boxes = new_pages[page_num] if page_num < len(new_pages) else []
                    if not elements_counted:
                        result["verificados"] += len(old_boxes) + len(new_boxes)
                    rem, add = _compare_page(old_boxes, new_boxes, thr_val)
                    removidos.extend(
                        {"pagina": page_num, "bbox": list(b[:4]), "texto": b[4]}
                        for b in rem
                    )
                    adicionados.extend(
                        {"pagina": page_num, "bbox": list(b[:4]), "texto": b[4]}
                        for b in add
                    )
                    if progress_callback:
                        done = j * max_pages + page_num + 1
                        progress = (done / total_steps) * 100
                        progress_callback(progress)
                    if cancel_callback and cancel_callback():
                        raise CancelledError()

                removidos, adicionados = _remove_unchanged(removidos, adicionados)
                removidos, adicionados = _remove_moved_same_text(
                    removidos, adicionados, dist=pos_tol
                )
                result = {
                    "removidos": removidos,
                    "adicionados": adicionados,
                    "verificados": result["verificados"],
                }
                elements_counted = True
                if cancel_callback and cancel_callback():
                    raise CancelledError()
                current = (
                    {(r["pagina"], tuple(r["bbox"])) for r in removidos},
                    {(a["pagina"], tuple(a["bbox"])) for a in adicionados},
                )
                if previous is not None and current == previous:
                    break
                previous = current
                if not removidos and not adicionados:
                    break
        finally:
            doc_new_resized.close()
        return result
