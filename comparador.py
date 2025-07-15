import fitz
from typing import List, Tuple, Dict


def _rotate_bbox(bbox: Tuple[float, float, float, float], w: float, h: float, rotation: int) -> Tuple[float, float, float, float]:
    """Rotate bounding box by multiples of 90 degrees clockwise."""
    x0, y0, x1, y1 = bbox
    rotation = rotation % 360
    if rotation == 90:
        return y0, w - x1, y1, w - x0
    if rotation == 180:
        return w - x1, h - y1, w - x0, h - y0
    if rotation == 270:
        return h - y1, x0, h - y0, x1
    return x0, y0, x1, y1


def _extract_bboxes(pdf_path: str, rotation: int = 0) -> List[List[Tuple[float, float, float, float, str]]]:
    """Return list of normalized bboxes per page from drawings and text blocks.

    Parameters
    ----------
    pdf_path: str
        File to load.
    rotation: int
        Optional clockwise rotation (multiples of 90 deg) to apply when
        extracting boxes.
    """
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        bboxes = []
        page_w, page_h = page.rect.width, page.rect.height
        norm_w, norm_h = (page_h, page_w) if rotation % 180 == 90 else (page_w, page_h)

        def _norm(rect: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
            rx0, ry0, rx1, ry1 = _rotate_bbox(rect, page_w, page_h, rotation)
            return rx0 / norm_w, ry0 / norm_h, rx1 / norm_w, ry1 / norm_h

        # Bounding boxes from drawing objects (no associated text)
        for drawing in page.get_drawings():
            r = drawing.get("rect")
            if r:
                bboxes.append((*_norm((r.x0, r.y0, r.x1, r.y1)), ""))

        # Bounding boxes from text blocks
        for block in page.get_text("blocks"):
            if len(block) >= 5:
                x0, y0, x1, y1, text = block[:5]
                bboxes.append((*_norm((float(x0), float(y0), float(x1), float(y1))), str(text).strip()))

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


def _compare_page(old_boxes: List[Tuple[float, float, float, float, str]],
                  new_boxes: List[Tuple[float, float, float, float, str]],
                  thr: float) -> Tuple[List[Tuple[float, float, float, float]],
                                       List[Tuple[float, float, float, float]]]:
    """Compare two lists of boxes returning removed and added ones.

    The coordinates are assumed to be normalized relative to page size, so the
    IoU comparison is independent of the original page dimensions.
    """
    matched_new = set()
    removed = []
    added = []

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
                    removed.append(ob[:4])
                    added.append(nb[:4])
                break
        if not found:
            removed.append(ob[:4])

    # Any new boxes not matched are considered additions
    added.extend(nb[:4] for i, nb in enumerate(new_boxes) if i not in matched_new)
    return removed, added


def comparar_pdfs(old_pdf: str, new_pdf: str, thr: float = 0.9,
                  old_rotation: int = 0, new_rotation: int = 0) -> Dict[str, List[Dict]]:
    """Compare two PDFs and return removed and added bounding boxes.

    Parameters
    ----------
    old_pdf, new_pdf: str
        Paths to the PDF files being compared.
    thr: float
        IoU threshold for considering boxes equal.
    old_rotation, new_rotation: int
        Optional clockwise rotation (multiples of 90 deg) to apply to
        ``old_pdf`` and ``new_pdf`` respectively before comparison.
    """
    old_pages = _extract_bboxes(old_pdf, old_rotation)
    new_pages = _extract_bboxes(new_pdf, new_rotation)
    max_pages = max(len(old_pages), len(new_pages))

    removidos = []
    adicionados = []
    for page_num in range(max_pages):
        old_boxes = old_pages[page_num] if page_num < len(old_pages) else []
        new_boxes = new_pages[page_num] if page_num < len(new_pages) else []
        rem, add = _compare_page(old_boxes, new_boxes, thr)
        removidos.extend({"pagina": page_num, "bbox": list(b)} for b in rem)
        adicionados.extend({"pagina": page_num, "bbox": list(b)} for b in add)

    return {"removidos": removidos, "adicionados": adicionados}
