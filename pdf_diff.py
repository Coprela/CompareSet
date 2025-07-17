from typing import Callable, Dict, List, Optional, Tuple

import io

import fitz
from PIL import Image, ImageChops


def _extract_bboxes(
    doc: fitz.Document,
    transforms: Optional[List[Tuple[float, float, float, float]]] = None,
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
                x0 = r.x0 * sx + tx
                y0 = r.y0 * sy + ty
                x1 = r.x1 * sx + tx
                y1 = r.y1 * sy + ty
                if x1 - x0 == 0:
                    x1 += 0.1
                if y1 - y0 == 0:
                    y1 += 0.1
                bboxes.append((x0, y0, x1, y1, ""))

        # Bounding boxes from images
        for img in page.get_images(full=True):
            xref = img[0]
            for r in page.get_image_rects(xref):
                bboxes.append(
                    (
                        r.x0 * sx + tx,
                        r.y0 * sy + ty,
                        r.x1 * sx + tx,
                        r.y1 * sy + ty,
                        "",
                    )
                )

        # Bounding boxes from individual words instead of full text blocks
        for word in page.get_text("words"):
            if len(word) >= 5:
                x0, y0, x1, y1, text = word[:5]
                bboxes.append(
                    (
                        float(x0) * sx + tx,
                        float(y0) * sy + ty,
                        float(x1) * sx + tx,
                        float(y1) * sy + ty,
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
    try:
        with open(path, "rb") as f:
            data = f.read()
        signed = b"/ByteRange" in data or b"/Type /Sig" in data
    except Exception:
        signed = False

    doc = fitz.open(path)
    if not signed:
        return doc

    cleaned = fitz.open()
    for i, page in enumerate(doc):
        new_page = cleaned.new_page(width=page.rect.width, height=page.rect.height)
        new_page.show_pdf_page(new_page.rect, doc, i)
    doc.close()
    return cleaned


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
    removidos: List[Dict], adicionados: List[Dict], eps: float = 0.01
) -> Tuple[List[Dict], List[Dict]]:
    """Filter out pairs of boxes that are effectively identical."""

    def _key(item: Dict) -> Tuple[int, Tuple[int, int, int, int]]:
        return (
            item["pagina"],
            tuple(int(round(v / eps)) for v in item["bbox"]),
        )

    removed_keys = {_key(r) for r in removidos}
    added_keys = {_key(a) for a in adicionados}
    duplicates = removed_keys & added_keys
    if not duplicates:
        return removidos, adicionados

    rem_filtered = [r for r in removidos if _key(r) not in duplicates]
    add_filtered = [a for a in adicionados if _key(a) not in duplicates]
    return rem_filtered, add_filtered


def _remove_moved_same_text(
    removidos: List[Dict],
    adicionados: List[Dict],
    dist: float = 1.0,
    size_eps: float = 0.5,
) -> Tuple[List[Dict], List[Dict]]:
    """Discard pairs with the same text that only moved slightly."""

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
                    if abs(rw - aw) <= size_eps and abs(rh - ah) <= size_eps:
                        match = i
                        break
        if match is None:
            filtered_rem.append(r)
        else:
            used_add.add(match)

    filtered_add = [a for i, a in enumerate(adicionados) if i not in used_add]
    return filtered_rem, filtered_add


def _remove_contained(boxes: List[Dict], eps: float = 0.01) -> List[Dict]:
    """Remove boxes fully contained within larger ones."""

    def _contains(a: List[float], b: List[float]) -> bool:
        return (
            a[0] <= b[0] + eps
            and a[1] <= b[1] + eps
            and a[2] >= b[2] - eps
            and a[3] >= b[3] - eps
        )

    filtered: List[Dict] = []
    for i, box in enumerate(boxes):
        contained = False
        for j, other in enumerate(boxes):
            if i == j:
                continue
            if _contains(other["bbox"], box["bbox"]):
                if (
                    (other["bbox"][2] - other["bbox"][0])
                    * (other["bbox"][3] - other["bbox"][1])
                    <=
                    (box["bbox"][2] - box["bbox"][0])
                    * (box["bbox"][3] - box["bbox"][1])
                ):
                    contained = True
                    break
        if not contained:
            filtered.append(box)
    return filtered


def _pix_to_pil(pix: fitz.Pixmap) -> Image.Image:
    """Convert a PyMuPDF Pixmap to a PIL Image."""
    mode = "RGB" if pix.alpha == 0 else "RGBA"
    return Image.frombytes(mode, (pix.width, pix.height), pix.samples)


def _boxes_from_diff(diff: Image.Image, thr: int = 10) -> List[Tuple[int, int, int, int]]:
    """Return bounding boxes from a binary difference image."""
    gray = diff.convert("L")
    w, h = gray.size
    data = gray.load()
    visited = [[False] * w for _ in range(h)]
    boxes = []
    for y in range(h):
        for x in range(w):
            if data[x, y] > thr and not visited[y][x]:
                stack = [(x, y)]
                visited[y][x] = True
                minx = maxx = x
                miny = maxy = y
                while stack:
                    cx, cy = stack.pop()
                    for nx, ny in (
                        (cx - 1, cy),
                        (cx + 1, cy),
                        (cx, cy - 1),
                        (cx, cy + 1),
                        (cx - 1, cy - 1),
                        (cx + 1, cy - 1),
                        (cx - 1, cy + 1),
                        (cx + 1, cy + 1),
                    ):
                        if (
                            0 <= nx < w
                            and 0 <= ny < h
                            and not visited[ny][nx]
                            and data[nx, ny] > thr
                        ):
                            visited[ny][nx] = True
                            stack.append((nx, ny))
                            minx = min(minx, nx)
                            maxx = max(maxx, nx)
                            miny = min(miny, ny)
                            maxy = max(maxy, ny)
                boxes.append((minx, miny, maxx + 1, maxy + 1))
    return boxes


def comparar_pdfs_imagem(
    old_pdf: str,
    new_pdf: str,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> Dict[str, List[Dict]]:
    """Compare PDFs rendering pages to images."""
    with fitz.open(old_pdf) as doc_old, fitz.open(new_pdf) as doc_new:
        max_pages = max(len(doc_old), len(doc_new))
        result = {"removidos": [], "adicionados": []}
        for i in range(max_pages):
            if i < len(doc_old):
                pix_old = doc_old[i].get_pixmap()
                img_old = _pix_to_pil(pix_old)
            else:
                rect = doc_new[i].rect
                img_old = Image.new("RGB", (int(rect.width), int(rect.height)), "white")
            if i < len(doc_new):
                pix_new = doc_new[i].get_pixmap()
                img_new = _pix_to_pil(pix_new)
            else:
                rect = doc_old[i].rect
                img_new = Image.new("RGB", (int(rect.width), int(rect.height)), "white")

            diff_rem = ImageChops.subtract(img_old, img_new)
            diff_add = ImageChops.subtract(img_new, img_old)
            rem_boxes = _boxes_from_diff(diff_rem)
            add_boxes = _boxes_from_diff(diff_add)
            for b in rem_boxes:
                result["removidos"].append({"pagina": i, "bbox": list(b), "texto": ""})
            for b in add_boxes:
                result["adicionados"].append({"pagina": i, "bbox": list(b), "texto": ""})
            if progress_callback:
                progress_callback(((i + 1) / max_pages) * 100)
        return result





def comparar_pdfs(
    old_pdf: str,
    new_pdf: str,
    thr: float = 0.9,
    adaptive: bool = False,
    progress_callback: Optional[Callable[[float], None]] = None,
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
    progress_callback : callable, optional
        Function called with a ``0-100`` progress percentage.
    """
    with _load_pdf_without_signatures(old_pdf) as doc_old, _load_pdf_without_signatures(
        new_pdf
    ) as doc_new:

        tolerance_pt = 72 / 25.4  # roughly one millimetre

        # compute transforms mapping new pages onto old pages
        transforms_new = []
        for i in range(len(doc_new)):
            if i < len(doc_old):
                rect_old = doc_old[i].rect
            else:
                rect_old = doc_new[i].rect
            rect_new = doc_new[i].rect
            width_diff = abs(rect_old.width - rect_new.width)
            height_diff = abs(rect_old.height - rect_new.height)
            if width_diff <= tolerance_pt and height_diff <= tolerance_pt:
                # pages are effectively the same size
                transforms_new.append((1.0, 1.0, 0.0, 0.0))
            elif rect_old.width != rect_new.width or rect_old.height != rect_new.height:
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
        result = {"removidos": [], "adicionados": []}
        previous: Optional[Tuple[set, set]] = None

        for j, thr_val in enumerate(thr_values):
            removidos = []
            adicionados = []
            for page_num in range(max_pages):
                old_boxes = old_pages[page_num] if page_num < len(old_pages) else []
                new_boxes = new_pages[page_num] if page_num < len(new_pages) else []
                rem, add = _compare_page(old_boxes, new_boxes, thr_val)
                removidos.extend(
                    {"pagina": page_num, "bbox": list(b[:4]), "texto": b[4]} for b in rem
                )
                adicionados.extend(
                    {"pagina": page_num, "bbox": list(b[:4]), "texto": b[4]} for b in add
                )
                if progress_callback:
                    done = j * max_pages + page_num + 1
                    progress = (done / total_steps) * 100
                    progress_callback(progress)

            removidos, adicionados = _remove_unchanged(removidos, adicionados)
            removidos, adicionados = _remove_moved_same_text(removidos, adicionados)
            removidos = _remove_contained(removidos)
            adicionados = _remove_contained(adicionados)
            result = {"removidos": removidos, "adicionados": adicionados}
            current = (
                {(r["pagina"], tuple(r["bbox"])) for r in removidos},
                {(a["pagina"], tuple(a["bbox"])) for a in adicionados},
            )
            if previous is not None and current == previous:
                break
            previous = current
            if not removidos and not adicionados:
                break

    return result
