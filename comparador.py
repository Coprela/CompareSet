import fitz
from typing import List, Tuple, Dict


def _boxes_close(a: Tuple[float, float, float, float],
                 b: Tuple[float, float, float, float],
                 prox: float) -> bool:
    """Return True if *b* is within ``prox`` distance from *a*."""
    expanded = (a[0] - prox, a[1] - prox, a[2] + prox, a[3] + prox)
    return not (
        expanded[2] < b[0] or expanded[0] > b[2] or
        expanded[3] < b[1] or expanded[1] > b[3]
    )


def _merge_dimension_boxes(boxes: List[Tuple[float, float, float, float]],
                            prox: float = 2.0) -> List[Tuple[float, float, float, float]]:
    """Merge nearby boxes which likely belong to the same dimension."""
    merged: List[Tuple[float, float, float, float]] = []
    used = [False] * len(boxes)
    for i, box in enumerate(boxes):
        if used[i]:
            continue
        x0, y0, x1, y1 = box
        changed = True
        while changed:
            changed = False
            for j in range(i + 1, len(boxes)):
                if used[j]:
                    continue
                if _boxes_close((x0, y0, x1, y1), boxes[j], prox):
                    bx = boxes[j]
                    x0 = min(x0, bx[0])
                    y0 = min(y0, bx[1])
                    x1 = max(x1, bx[2])
                    y1 = max(y1, bx[3])
                    used[j] = True
                    changed = True
        merged.append((x0, y0, x1, y1))
    return merged


def _extract_bboxes(pdf_path: str, merge_prox: float = 2.0) -> List[List[Tuple[float, float, float, float]]]:
    """Return list of bboxes per page from drawing objects."""
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        bboxes = []
        for drawing in page.get_drawings():
            r = drawing.get("rect")
            if r:
                bboxes.append((r.x0, r.y0, r.x1, r.y1))
        if merge_prox is not None:
            bboxes = _merge_dimension_boxes(bboxes, prox=merge_prox)
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


def _compare_page(old_boxes: List[Tuple[float, float, float, float]],
                  new_boxes: List[Tuple[float, float, float, float]],
                  thr: float) -> Tuple[List[Tuple[float, float, float, float]],
                                       List[Tuple[float, float, float, float]]]:
    matched_new = set()
    removed = []
    for ob in old_boxes:
        found = False
        for i, nb in enumerate(new_boxes):
            if i in matched_new:
                continue
            if _iou(ob, nb) >= thr:
                matched_new.add(i)
                found = True
                break
        if not found:
            removed.append(ob)

    added = [nb for i, nb in enumerate(new_boxes) if i not in matched_new]
    return removed, added


def comparar_pdfs(old_pdf: str, new_pdf: str, thr: float = 0.9,
                  merge_prox: float = 2.0) -> Dict[str, List[Dict]]:
    """Compare two PDFs and return removed and added bounding boxes."""
    old_pages = _extract_bboxes(old_pdf, merge_prox)
    new_pages = _extract_bboxes(new_pdf, merge_prox)
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
