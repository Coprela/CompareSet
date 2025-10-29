# compareset_mvp.py
# --------------------------------------------------------------------------------------
# Minimal, testable MVP for Compare 7 — raster diff → vector rectangle overlays in PDF.
# Output: a single 2-page PDF (Page 1: OLD with red boxes; Page 2: NEW with green boxes)
#
# requirements.txt (exact lines):
# pymupdf
# opencv-python
# numpy
# --------------------------------------------------------------------------------------

import sys
import os
import argparse
import traceback

# Dependency check (friendly message if missing)
MISSING = []
try:
    import fitz  # PyMuPDF
except Exception as e:
    MISSING.append(("pymupdf", e))
try:
    import cv2
except Exception as e:
    MISSING.append(("opencv-python", e))
try:
    import numpy as np
except Exception as e:
    MISSING.append(("numpy", e))

if MISSING:
    sys.stderr.write("Missing dependencies:\n")
    for name, err in MISSING:
        sys.stderr.write(f" - {name}: {err}\n")
    sys.stderr.write("\nPlease install them with:\n    pip install -r requirements.txt\n")
    sys.exit(2)

# --------------------------------------------------------------------------------------
# FIXED INTERNAL CONSTANTS (no UI knobs)
# --------------------------------------------------------------------------------------
DPI = 300
BLUR_KSIZE = 3
THRESH = 25
MORPH_KERNEL = 3
DILATE_ITERS = 2
ERODE_ITERS = 1
MIN_AREA = 36  # pixels^2

# Stroke styling
STROKE_WIDTH_PT = 0.8
RED = (1.0, 0.0, 0.0)
GREEN = (0.0, 1.0, 0.0)
STROKE_OPACITY = 0.6  # translucent stroke


# --------------------------------------------------------------------------------------
# Utilities
# --------------------------------------------------------------------------------------
def log(msg: str):
    print(f"[Compare7] {msg}")


def load_pdf(path: str) -> fitz.Document:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    if not path.lower().endswith(".pdf"):
        raise ValueError(f"Not a PDF: {path}")
    return fitz.open(path)


def zoom_from_dpi(dpi: int) -> float:
    return dpi / 72.0


def render_page_pix(doc: fitz.Document, page_index: int, dpi: int):
    """
    Render a page to a grayscale numpy uint8 image.
    Returns (img_gray[h,w], page_pix_w, page_pix_h)
    """
    page = doc.load_page(page_index)
    z = zoom_from_dpi(dpi)
    mat = fitz.Matrix(z, z)
    # grayscale colorspace
    cs = fitz.csGRAY
    pix = page.get_pixmap(matrix=mat, colorspace=cs, alpha=False)
    w, h = pix.width, pix.height
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(h, w)
    return img, w, h


def letterbox_to_common_canvas(img_a, img_b):
    """
    Given two grayscale images (H×W), place them onto a common black canvas
    of size (maxH, maxW), centered. Return:
      canvas_a, canvas_b, offsets_a(x,y), offsets_b(x,y), sizes_a(w,h), sizes_b(w,h)
    Offsets are (x_offset, y_offset) top-left of original image inside canvas.
    """
    ha, wa = img_a.shape
    hb, wb = img_b.shape
    H = max(ha, hb)
    W = max(wa, wb)

    canvas_a = np.zeros((H, W), dtype=np.uint8)
    canvas_b = np.zeros((H, W), dtype=np.uint8)

    xa = (W - wa) // 2
    ya = (H - ha) // 2
    xb = (W - wb) // 2
    yb = (H - hb) // 2

    canvas_a[ya:ya + ha, xa:xa + wa] = img_a
    canvas_b[yb:yb + hb, xb:xb + wb] = img_b

    return (canvas_a, canvas_b, (xa, ya), (xb, yb), (wa, ha), (wb, hb))


def compute_diff_boxes(img_old, img_new):
    """
    Compute difference bounding boxes (in canvas pixel coordinates).
    Returns list of boxes as (x, y, w, h) with area >= MIN_AREA.
    """
    # 1) blur
    blur_old = cv2.GaussianBlur(img_old, (BLUR_KSIZE, BLUR_KSIZE), 0)
    blur_new = cv2.GaussianBlur(img_new, (BLUR_KSIZE, BLUR_KSIZE), 0)

    # 2) absdiff
    diff = cv2.absdiff(blur_old, blur_new)

    # 3) threshold
    _, th = cv2.threshold(diff, THRESH, 255, cv2.THRESH_BINARY)

    # 4) morphology (close)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (MORPH_KERNEL, MORPH_KERNEL))
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)

    # 5) dilate then erode
    th = cv2.dilate(th, kernel, iterations=DILATE_ITERS)
    th = cv2.erode(th, kernel, iterations=ERODE_ITERS)

    # 6) contours → bboxes
    contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w * h >= MIN_AREA:
            boxes.append((x, y, w, h))
    return boxes


def rects_overlap_or_touch(a, b):
    """
    Return True if rectangles a and b overlap OR touch edges.
    a, b are (x, y, w, h)
    """
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh

    # If one is completely to the left/right/above/below with a gap, they don't touch.
    # "Touch" means edges can coincide: use < 0 for gaps; <= 0 means touching counts as merge.
    if ax2 < bx1 or bx2 < ax1:
        return False
    if ay2 < by1 or by2 < ay1:
        return False
    return True  # overlap or touch


def merge_two(a, b):
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    nx1 = min(ax1, bx1)
    ny1 = min(ay1, by1)
    nx2 = max(ax2, bx2)
    ny2 = max(ay2, by2)
    return (nx1, ny1, nx2 - nx1, ny2 - ny1)


def merge_touching_rects(rects):
    if not rects:
        return []
    rects = rects[:]
    merged = True
    while merged:
        merged = False
        new_rects = []
        used = [False] * len(rects)
        for i in range(len(rects)):
            if used[i]:
                continue
            r = rects[i]
            for j in range(i + 1, len(rects)):
                if used[j]:
                    continue
                s = rects[j]
                if rects_overlap_or_touch(r, s):
                    r = merge_two(r, s)
                    used[j] = True
                    merged = True
            used[i] = True
            new_rects.append(r)
        rects = new_rects
    return rects


def clip_box_to_page_pixels(box, page_w, page_h, x_off, y_off):
    """
    Convert a box in CANVAS pixel coordinates into local PAGE pixel coordinates
    by subtracting (x_off, y_off) and clipping to [0, page_w) x [0, page_h).
    Returns (x,y,w,h) in local page pixels, or None if completely outside.
    """
    x, y, w, h = box
    # Translate
    x -= x_off
    y -= y_off
    # Clip
    x2 = x + w
    y2 = y + h
    # Fully outside?
    if x2 <= 0 or y2 <= 0 or x >= page_w or y >= page_h:
        return None
    # clamp
    nx = max(0, x)
    ny = max(0, y)
    nx2 = min(page_w, x2)
    ny2 = min(page_h, y2)
    return (int(nx), int(ny), int(nx2 - nx), int(ny2 - ny))


def pixels_to_pdf_rects(rects_pixels, page: fitz.Page, zoom: float):
    """
    Convert local page pixel rectangles (x,y,w,h) into PDF point rectangles (fitz.Rect),
    using the render zoom used for that page (pixels = points * zoom).
    """
    pdf_rects = []
    inv = 1.0 / zoom
    for (x, y, w, h) in rects_pixels:
        # pixel -> point
        px1 = x * inv
        py1 = y * inv
        px2 = (x + w) * inv
        py2 = (y + h) * inv
        # PyMuPDF uses y downward as well in page space; direct mapping is fine.
        pdf_rects.append(fitz.Rect(px1, py1, px2, py2))
    return pdf_rects


def draw_rects(page: fitz.Page, rects, color_rgb, width_pt, stroke_opacity):
    """
    Draw stroke-only rectangles (no fill) with translucency.
    """
    # Use page.draw_rect with stroke_opacity to ensure translucency.
    for r in rects:
        page.draw_rect(
            r,
            color=color_rgb,
            fill=None,
            width=width_pt,
            stroke_opacity=stroke_opacity,
            overlay=True
        )


def compare_first_pages(old_path: str, new_path: str):
    """
    MVP: compare ONLY the first page of each PDF and return:
      - old_doc (opened)
      - new_doc (opened)
      - rects_old_pdf: list[fitz.Rect] to draw on old page
      - rects_new_pdf: list[fitz.Rect] to draw on new page (same regions mapped)
      - page indices used (0,0)
    """
    old_doc = load_pdf(old_path)
    new_doc = load_pdf(new_path)

    if old_doc.page_count > 1 or new_doc.page_count > 1:
        log("Warning: multi-page PDFs detected. MVP will process ONLY the first page (index 0).")

    # Render both first pages
    log("Rendering pages at fixed DPI...")
    img_old, w_old, h_old = render_page_pix(old_doc, 0, DPI)
    img_new, w_new, h_new = render_page_pix(new_doc, 0, DPI)

    # Put both on a common canvas (letterbox style)
    (can_old, can_new, off_old, off_new, size_old, size_new) = letterbox_to_common_canvas(img_old, img_new)
    (xa, ya) = off_old
    (xb, yb) = off_new
    (pw_old, ph_old) = size_old
    (pw_new, ph_new) = size_new

    if (w_old, h_old) != (w_new, h_new):
        log(f"Different render sizes: old=({w_old}x{h_old}), new=({w_new}x{h_new}). Using letterbox alignment.")

    # Diff on common canvas
    log("Computing raster differences...")
    boxes = compute_diff_boxes(can_old, can_new)
    log(f"Found {len(boxes)} raw boxes.")

    # Merge touching/overlapping
    boxes_merged = merge_touching_rects(boxes)
    log(f"Merged to {len(boxes_merged)} boxes.")

    # Map canvas boxes back to local page pixel coords and then to PDF rects
    z = zoom_from_dpi(DPI)
    # OLD page boxes (translate by off_old, clip to old page size)
    local_old = []
    for b in boxes_merged:
        clipped = clip_box_to_page_pixels(b, pw_old, ph_old, xa, ya)
        if clipped:
            local_old.append(clipped)
    # NEW page boxes
    local_new = []
    for b in boxes_merged:
        clipped = clip_box_to_page_pixels(b, pw_new, ph_new, xb, yb)
        if clipped:
            local_new.append(clipped)

    rects_old_pdf = pixels_to_pdf_rects(local_old, old_doc.load_page(0), z)
    rects_new_pdf = pixels_to_pdf_rects(local_new, new_doc.load_page(0), z)

    log(f"Page 0: old rects = {len(rects_old_pdf)}, new rects = {len(rects_new_pdf)}")

    return old_doc, new_doc, rects_old_pdf, rects_new_pdf, 0, 0


def build_two_page_output(old_doc: fitz.Document,
                          new_doc: fitz.Document,
                          old_page_index: int,
                          new_page_index: int,
                          rects_old_pdf,
                          rects_new_pdf,
                          out_path: str):
    """
    Create a new PDF with exactly two pages:
      Page 1: copy of OLD page (old_page_index) with red rectangles
      Page 2: copy of NEW page (new_page_index) with green rectangles
    """
    # Create an empty output
    out = fitz.open()

    # Copy pages as templates
    old_page = old_doc.load_page(old_page_index)
    new_page = new_doc.load_page(new_page_index)

    # Insert copies into output
    out.insert_pdf(old_doc, from_page=old_page_index, to_page=old_page_index)
    out.insert_pdf(new_doc, from_page=new_page_index, to_page=new_page_index)

    # Now draw rectangles on the inserted pages
    out_old_page = out.load_page(0)  # first page
    out_new_page = out.load_page(1)  # second page

    if rects_old_pdf:
        draw_rects(out_old_page, rects_old_pdf, RED, STROKE_WIDTH_PT, STROKE_OPACITY)
    if rects_new_pdf:
        draw_rects(out_new_page, rects_new_pdf, GREEN, STROKE_WIDTH_PT, STROKE_OPACITY)

    out.save(out_path, deflate=True)
    out.close()


def main():
    parser = argparse.ArgumentParser(
        description="Compare 7 MVP — raster diff with vector rectangle overlays. Output: 2-page PDF."
    )
    parser.add_argument("--old", required=True, help="Path to OLD/original PDF")
    parser.add_argument("--new", required=True, help="Path to NEW/revised PDF")
    parser.add_argument("--out", required=False, default="CompareSet_Result.pdf", help="Output PDF path")
    args = parser.parse_args()

    try:
        log(f"Opening PDFs:\n  OLD: {args.old}\n  NEW: {args.new}")
        old_doc, new_doc, rects_old_pdf, rects_new_pdf, i_old, i_new = compare_first_pages(args.old, args.new)

        # Build final 2-page output
        out_path = args.out
        log("Building 2-page output PDF...")
        build_two_page_output(old_doc, new_doc, i_old, i_new, rects_old_pdf, rects_new_pdf, out_path)

        if len(rects_old_pdf) == 0 and len(rects_new_pdf) == 0:
            log("No diffs on page 0.")

        old_doc.close()
        new_doc.close()

        log(f"Done. Output saved to: {out_path}")

    except SystemExit:
        raise
    except Exception as e:
        sys.stderr.write("[Compare7] ERROR: {}: {}\n".format(type(e).__name__, e))
        tb = traceback.format_exc(limit=2)
        sys.stderr.write(tb + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
