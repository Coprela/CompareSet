import fitz
from typing import List, Tuple, Dict, Optional


def _extract_bboxes(doc: fitz.Document,
                    transforms: Optional[List[Tuple[float, float, float, float]]] = None
                    ) -> List[List[Tuple[float, float, float, float, str]]]:
    """Return list of bboxes per page from drawings and text blocks.

    Parameters
    ----------
    doc: fitz.Document
        Opened document whose pages will be processed.
    transforms: list of tuples(scale_x, scale_y, trans_x, trans_y), optional
        Transformations applied to each page's coordinates.
    """
    pages: List[List[Tuple[float, float, float, float, str]]] = []
    for i, page in enumerate(doc):
        if transforms and i < len(transforms):
            sx, sy, tx, ty = transforms[i]
        else:
            sx = sy = 1.0
            tx = ty = 0.0
        bboxes = []
        # Bounding boxes from drawing objects (no associated text)
        for drawing in page.get_drawings():
            r = drawing.get("rect")
            if r:
                bboxes.append((r.x0 * sx + tx, r.y0 * sy + ty,
                               r.x1 * sx + tx, r.y1 * sy + ty, ""))

        # Bounding boxes from text blocks
        for block in page.get_text("blocks"):
            if len(block) >= 5:
                x0, y0, x1, y1, text = block[:5]
                bboxes.append((float(x0) * sx + tx, float(y0) * sy + ty,
                               float(x1) * sx + tx, float(y1) * sy + ty,
                               str(text).strip()))

        pages.append(bboxes)
    return pages


def _iou(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
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


def _boxes_close(a: Tuple[float, float, float, float],
                 b: Tuple[float, float, float, float],
                 tol: float) -> bool:
    """Return True if all coordinates differ less than *tol* points."""
    return all(abs(a[i] - b[i]) <= tol for i in range(4))


def _compare_page(old_boxes: List[Tuple[float, float, float, float, str]],
                  new_boxes: List[Tuple[float, float, float, float, str]],
                  thr: float,
                  same_text_iou: float = 0.98,
                  trans_tol: float = 0.0) -> Tuple[List[Tuple[float, float, float, float]],
                                                   List[Tuple[float, float, float, float]]]:
    """Compare two lists of boxes returning removed and added ones.

    Parameters
    ----------
    thr: float
        IoU threshold for considering two boxes the same.
    same_text_iou: float
        Minimum IoU for boxes with identical text to be treated as unchanged.
    trans_tol: float
        Maximum coordinate difference to ignore when texts are identical.
    """
    matched_new = set()
    removed = []
    added = []

    for ob in old_boxes:
        found = False
        for i, nb in enumerate(new_boxes):
            if i in matched_new:
                continue
            iou_val = _iou(ob[:4], nb[:4])
            same_text = ob[4].strip() == nb[4].strip()
            if same_text:
                if trans_tol > 0 and _boxes_close(ob[:4], nb[:4], trans_tol):
                    matched_new.add(i)
                    found = True
                    break
                if iou_val >= same_text_iou:
                    matched_new.add(i)
                    found = True
                    break
            if iou_val >= thr:
                matched_new.add(i)
                found = True
                if not same_text:
                    # Geometry matches but text differs
                    removed.append(ob[:4])
                    added.append(nb[:4])
                break
        if not found:
            removed.append(ob[:4])

    # Any new boxes not matched are considered additions
    added.extend(nb[:4] for i, nb in enumerate(new_boxes) if i not in matched_new)
    return removed, added


def comparar_pdfs(old_pdf: str,
                  new_pdf: str,
                  thr: float = 0.9,
                  same_text_iou: float = 0.98,
                  trans_tol: float = 0.5) -> Dict[str, List[Dict]]:
"""Compare two PDFs and return removed and added bounding boxes.

    The function takes page dimensions into account. When pages have
    different sizes they are scaled and translated so that comparisons
    happen in a shared coordinate space based on the old PDF pages.

    Parameters
    ----------
    thr: float
        IoU threshold for matching boxes regardless of text.
    same_text_iou: float
        Minimum IoU for boxes with identical text to be considered equal.
    trans_tol: float
        Maximum coordinate difference allowed for boxes with identical text.
    """
    doc_old = fitz.open(old_pdf)
    doc_new = fitz.open(new_pdf)

    # compute transforms mapping new pages onto old pages
    transforms_new = []
    for i in range(len(doc_new)):
        if i < len(doc_old):
            rect_old = doc_old[i].rect
        else:
            rect_old = doc_new[i].rect
        rect_new = doc_new[i].rect
        if rect_old.width != rect_new.width or rect_old.height != rect_new.height:
            sx = rect_old.width / rect_new.width
            sy = rect_old.height / rect_new.height
            s = min(sx, sy)
            tx = (rect_old.width - rect_new.width * s) / 2.0
            ty = (rect_old.height - rect_new.height * s) / 2.0
            transforms_new.append((s, s, tx, ty))
        else:
            transforms_new.append((1.0, 1.0, 0.0, 0.0))

    old_pages = _extract_bboxes(doc_old)
    new_pages = _extract_bboxes(doc_new, transforms_new)
    max_pages = max(len(old_pages), len(new_pages))

    removidos = []
    adicionados = []
    for page_num in range(max_pages):
        old_boxes = old_pages[page_num] if page_num < len(old_pages) else []
        new_boxes = new_pages[page_num] if page_num < len(new_pages) else []
        rem, add = _compare_page(old_boxes, new_boxes, thr,
                                same_text_iou=same_text_iou,
                                trans_tol=trans_tol)
        removidos.extend({"pagina": page_num, "bbox": list(b)} for b in rem)
        adicionados.extend({"pagina": page_num, "bbox": list(b)} for b in add)

    return {"removidos": removidos, "adicionados": adicionados}
