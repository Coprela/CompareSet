import fitz
import string
from typing import List, Tuple, Dict


def normalize_text(text: str) -> str:
    """Return normalized text.

    Leading and trailing whitespace is removed, text is lowercased and
    punctuation characters are stripped.
    """
    text = text.strip().lower()
    return text.translate(str.maketrans("", "", string.punctuation))


def _extract_bboxes(pdf_path: str) -> List[List[Tuple[float, float, float, float, str]]]:
    """Return list of bboxes per page from drawings and text blocks."""
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        bboxes = []
        # Bounding boxes from drawing objects (no associated text)
        for drawing in page.get_drawings():
            r = drawing.get("rect")
            if r:
                bboxes.append((r.x0, r.y0, r.x1, r.y1, ""))

        # Bounding boxes from text blocks
        for block in page.get_text("blocks"):
            if len(block) >= 5:
                x0, y0, x1, y1, text = block[:5]
                bboxes.append((float(x0), float(y0), float(x1), float(y1), str(text).strip()))

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
    """Compare two lists of boxes returning removed and added ones."""
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
                if normalize_text(ob[4]) != normalize_text(nb[4]):
                    # Geometry matches but text differs
                    removed.append(ob[:4])
                    added.append(nb[:4])
                break
        if not found:
            removed.append(ob[:4])

    # Any new boxes not matched are considered additions
    added.extend(nb[:4] for i, nb in enumerate(new_boxes) if i not in matched_new)
    return removed, added


def comparar_pdfs(old_pdf: str, new_pdf: str, thr: float = 0.9) -> Dict[str, List[Dict]]:
    """Compare two PDFs and return removed and added bounding boxes.

    Parameters
    ----------
    old_pdf : str
        Path to the older revision.
    new_pdf : str
        Path to the newer revision.
    thr : float, optional
        Intersection over Union (IoU) threshold used to match boxes. The
        default of ``0.9`` works well for most documents but can be adjusted
        if needed.
    """
    old_pages = _extract_bboxes(old_pdf)
    new_pages = _extract_bboxes(new_pdf)
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
